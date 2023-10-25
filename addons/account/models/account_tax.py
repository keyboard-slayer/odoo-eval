# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, Command
from odoo.osv import expression
from odoo.tools.float_utils import float_round
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import clean_context, formatLang
from odoo.tools import frozendict, groupby

from collections import Counter, defaultdict
from markupsafe import Markup

import ast
import math
import re


TYPE_TAX_USE = [
    ('sale', 'Sales'),
    ('purchase', 'Purchases'),
    ('none', 'None'),
]


class AccountTaxGroup(models.Model):
    _name = 'account.tax.group'
    _description = 'Tax Group'
    _order = 'sequence asc, id'
    _check_company_auto = True
    _check_company_domain = models.check_company_domain_parent_of

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    tax_payable_account_id = fields.Many2one(
        comodel_name='account.account',
        check_company=True,
        string='Tax Payable Account',
        help="Tax current account used as a counterpart to the Tax Closing Entry when in favor of the authorities.")
    tax_receivable_account_id = fields.Many2one(
        comodel_name='account.account',
        check_company=True,
        string='Tax Receivable Account',
        help="Tax current account used as a counterpart to the Tax Closing Entry when in favor of the company.")
    advance_tax_payment_account_id = fields.Many2one(
        comodel_name='account.account',
        check_company=True,
        string='Tax Advance Account',
        help="Downpayments posted on this account will be considered by the Tax Closing Entry.")
    country_id = fields.Many2one(
        string="Country",
        comodel_name='res.country',
        compute='_compute_country_id', store=True, readonly=False, precompute=True,
        help="The country for which this tax group is applicable.",
    )
    country_code = fields.Char(related="country_id.code")
    preceding_subtotal = fields.Char(
        string="Preceding Subtotal",
        help="If set, this value will be used on documents as the label of a subtotal excluding this tax group before displaying it. " \
             "If not set, the tax group will be displayed after the 'Untaxed amount' subtotal.",
    )

    @api.depends('company_id.account_fiscal_country_id')
    def _compute_country_id(self):
        for group in self:
            group.country_id = group.company_id.account_fiscal_country_id or group.company_id.country_id

    @api.model
    def _check_misconfigured_tax_groups(self, company, countries):
        """ Searches the tax groups used on the taxes from company in countries that don't have
        at least a tax payable account, a tax receivable account or an advance tax payment account.

        :return: A boolean telling whether or not there are misconfigured groups for any
                 of these countries, in this company
        """
        return bool(self.env['account.tax'].search([
            *self.env['account.tax']._check_company_domain(company),
            ('country_id', 'in', countries.ids),
            '|',
            ('tax_group_id.tax_payable_account_id', '=', False),
            ('tax_group_id.tax_receivable_account_id', '=', False),
        ], limit=1))


class AccountTax(models.Model):
    _name = 'account.tax'
    _inherit = ['mail.thread']
    _description = 'Tax'
    _order = 'sequence,id'
    _check_company_auto = True
    _rec_names_search = ['name', 'description', 'invoice_label']
    _check_company_domain = models.check_company_domain_parent_of

    name = fields.Char(string='Tax Name', required=True, translate=True, tracking=True)
    name_searchable = fields.Char(store=False, search='_search_name',
          help="This dummy field lets us use another search method on the field 'name'."
               "This allows more freedom on how to search the 'name' compared to 'filter_domain'."
               "See '_search_name' and '_parse_name_search' for why this is not possible with 'filter_domain'.")
    type_tax_use = fields.Selection(TYPE_TAX_USE, string='Tax Type', required=True, default="sale",
        help="Determines where the tax is selectable. Note: 'None' means a tax can't be used by itself, however it can still be used in a group. 'adjustment' is used to perform tax adjustment.")
    tax_scope = fields.Selection([('service', 'Services'), ('consu', 'Goods')], string="Tax Scope", help="Restrict the use of taxes to a type of product.")
    amount_type = fields.Selection(default='percent', string="Tax Computation", required=True,
        selection=[('group', 'Group of Taxes'), ('fixed', 'Fixed'), ('percent', 'Percentage of Price'), ('division', 'Percentage of Price Tax Included')],
        help="""
    - Group of Taxes: The tax is a set of sub taxes.
    - Fixed: The tax amount stays the same whatever the price.
    - Percentage of Price: The tax amount is a % of the price:
        e.g 100 * (1 + 10%) = 110 (not price included)
        e.g 110 / (1 + 10%) = 100 (price included)
    - Percentage of Price Tax Included: The tax amount is a division of the price:
        e.g 180 / (1 - 10%) = 200 (not price included)
        e.g 200 * (1 - 10%) = 180 (price included)
        """)
    active = fields.Boolean(default=True, help="Set active to false to hide the tax without removing it.")
    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=True, default=lambda self: self.env.company)
    children_tax_ids = fields.Many2many('account.tax',
        'account_tax_filiation_rel', 'parent_tax', 'child_tax',
        check_company=True,
        string='Children Taxes')
    sequence = fields.Integer(required=True, default=1,
        help="The sequence field is used to define order in which the tax lines are applied.")
    amount = fields.Float(required=True, digits=(16, 4), default=0.0, tracking=True)
    description = fields.Char(string='Description', translate=True)
    invoice_label = fields.Char(string='Label on Invoices', translate=True)
    price_include = fields.Boolean(string='Included in Price', default=False,
        help="Check this if the price you use on the product and invoices includes this tax.")
    include_base_amount = fields.Boolean(string='Affect Base of Subsequent Taxes', default=False, tracking=True,
        help="If set, taxes with a higher sequence than this one will be affected by it, provided they accept it.")
    is_base_affected = fields.Boolean(
        string="Base Affected by Previous Taxes",
        default=True,
        tracking=True,
        help="If set, taxes with a lower sequence might affect this one, provided they try to do it.")
    analytic = fields.Boolean(string="Include in Analytic Cost", help="If set, the amount computed by this tax will be assigned to the same analytic account as the invoice line (if any)")
    tax_group_id = fields.Many2one(
        comodel_name='account.tax.group',
        string="Tax Group",
        compute='_compute_tax_group_id', readonly=False, store=True,
        required=True, precompute=True,
        domain="[('country_id', 'in', (country_id, False))]")
    # Technical field to make the 'tax_exigibility' field invisible if the same named field is set to false in 'res.company' model
    hide_tax_exigibility = fields.Boolean(string='Hide Use Cash Basis Option', related='company_id.tax_exigibility', readonly=True)
    tax_exigibility = fields.Selection(
        [('on_invoice', 'Based on Invoice'),
         ('on_payment', 'Based on Payment'),
        ], string='Tax Exigibility', default='on_invoice',
        help="Based on Invoice: the tax is due as soon as the invoice is validated.\n"
        "Based on Payment: the tax is due as soon as the payment of the invoice is received.")
    cash_basis_transition_account_id = fields.Many2one(string="Cash Basis Transition Account",
        check_company=True,
        domain="[('deprecated', '=', False)]",
        comodel_name='account.account',
        help="Account used to transition the tax amount for cash basis taxes. It will contain the tax amount as long as the original invoice has not been reconciled ; at reconciliation, this amount cancelled on this account and put on the regular tax account.")
    invoice_repartition_line_ids = fields.One2many(
        string="Distribution for Invoices",
        comodel_name="account.tax.repartition.line",
        compute='_compute_invoice_repartition_line_ids', store=True, readonly=False,
        inverse_name="tax_id",
        domain=[('document_type', '=', 'invoice')],
        help="Distribution when the tax is used on an invoice",
    )
    refund_repartition_line_ids = fields.One2many(
        string="Distribution for Refund Invoices",
        comodel_name="account.tax.repartition.line",
        compute='_compute_refund_repartition_line_ids', store=True, readonly=False,
        inverse_name="tax_id",
        domain=[('document_type', '=', 'refund')],
        help="Distribution when the tax is used on a refund",
    )
    repartition_line_ids = fields.One2many(
        string="Distribution",
        comodel_name="account.tax.repartition.line",
        inverse_name="tax_id",
        copy=True,
    )
    country_id = fields.Many2one(
        string="Country",
        comodel_name='res.country',
        compute='_compute_country_id', readonly=False, store=True,
        required=True, precompute=True,
        help="The country for which this tax is applicable.",
    )
    country_code = fields.Char(related='country_id.code', readonly=True)
    is_used = fields.Boolean(string="Tax used", compute='_compute_is_used')
    repartition_lines_str = fields.Char(string="Repartition Lines", tracking=True, compute='_compute_repartition_lines_str')

    @api.constrains('company_id', 'name', 'type_tax_use', 'tax_scope')
    def _constrains_name(self):
        domains = []
        for record in self:
            if record.type_tax_use != 'none':
                domains.append([
                    ('company_id', 'child_of', record.company_id.root_id.id),
                    ('name', '=', record.name),
                    ('type_tax_use', '=', record.type_tax_use),
                    ('tax_scope', '=', record.tax_scope),
                    ('country_id', '=', record.country_id.id),
                    ('id', '!=', record.id),
                ])
        if duplicates := self.search(expression.OR(domains)):
            raise ValidationError(
                _("Tax names must be unique!")
                + "\n" + "\n".join(f"- {duplicate.name} in {duplicate.company_id.name}" for duplicate in duplicates)
            )

    @api.constrains('tax_group_id')
    def validate_tax_group_id(self):
        for record in self:
            if record.tax_group_id.country_id and record.tax_group_id.country_id != record.country_id:
                raise ValidationError(_("The tax group must have the same country_id as the tax using it."))

    @api.constrains('amount_type', 'type_tax_use', 'price_include', 'include_base_amount')
    def _constrains_fields_after_tax_is_used(self):
        for tax in self:
            if tax.is_used:
                raise ValidationError(_("This tax has been used in transactions. For that reason, it is forbidden to modify this field."))

    @api.depends('company_id.account_fiscal_country_id')
    def _compute_country_id(self):
        for tax in self:
            tax.country_id = tax.company_id.account_fiscal_country_id or tax.company_id.country_id or tax.country_id

    @api.depends('company_id', 'country_id')
    def _compute_tax_group_id(self):
        by_country_company = defaultdict(self.browse)
        for tax in self:
            if (
                not tax.tax_group_id
                or tax.tax_group_id.country_id != tax.country_id
                or tax.tax_group_id.company_id != tax.company_id
            ):
                by_country_company[(tax.country_id, tax.company_id)] += tax
        for (country, company), taxes in by_country_company.items():
            taxes.tax_group_id = self.env['account.tax.group'].search([
                *self.env['account.tax.group']._check_company_domain(company),
                ('country_id', '=', country.id),
            ], limit=1) or self.env['account.tax.group'].search([
                *self.env['account.tax.group']._check_company_domain(company),
                ('country_id', '=', False),
            ], limit=1)

    def _hook_compute_is_used(self):
        '''
            To be overriden to add taxed transactions in the computation of `is_used`
            Should return a Counter containing a dictionary {record: int} where
            the record is an account.tax object. The int should be greater than 0
            if the tax is used in a transaction.
        '''
        return Counter()

    def _compute_is_used(self):
        taxes_in_transactions_ctr = (
            Counter(dict(self.env['account.move.line']._read_group([], groupby=['tax_ids'], aggregates=['__count']))) +
            Counter(dict(self.env['account.reconcile.model.line']._read_group([], groupby=['tax_ids'], aggregates=['__count']))) +
            self._hook_compute_is_used()
        )
        for tax in self:
            tax.is_used = bool(taxes_in_transactions_ctr[tax])

    @api.depends('repartition_line_ids.account_id', 'repartition_line_ids.factor_percent', 'repartition_line_ids.use_in_tax_closing', 'repartition_line_ids.tag_ids')
    def _compute_repartition_lines_str(self):
        for tax in self:
            repartition_lines_str = tax.repartition_lines_str or ""
            if tax.is_used:
                for repartition_line in tax.repartition_line_ids:
                    repartition_line_info = {
                        _('id'): repartition_line.id,
                        _('Factor Percent'): repartition_line.factor_percent,
                        _('Account'): repartition_line.account_id.name or _('None'),
                        _('Tax Grids'): repartition_line.tag_ids.mapped('name') or _('None'),
                        _('Use in tax closing'): _('True') if repartition_line.use_in_tax_closing else _('False'),
                    }
                    repartition_lines_str += str(repartition_line_info) + '//'
                repartition_lines_str = repartition_lines_str.strip('//')
            tax.repartition_lines_str = repartition_lines_str

    def _message_log_repartition_lines(self, old_value_str, new_value_str):
        self.ensure_one()
        if not self.is_used:
            return

        old_values = old_value_str.split('//')
        new_values = new_value_str.split('//')

        kwargs = {}
        for old_value, new_value in zip(old_values, new_values):
            if old_value != new_value:
                old_value = ast.literal_eval(old_value)
                new_value = ast.literal_eval(new_value)
                diff_keys = [key for key in old_value if old_value[key] != new_value[key]]
                repartition_line = self.env['account.tax.repartition.line'].search([('id', '=', new_value['id'])])
                body = Markup("<b>{type}</b> {rep} {seq}:<ul class='mb-0 ps-4'>{changes}</ul>").format(
                    type=repartition_line.document_type.capitalize(),
                    rep=_('repartition line'),
                    seq=repartition_line.sequence + 1,
                    changes=Markup().join(
                        [Markup("""
                            <li>
                                <span class='o-mail-Message-trackingOld me-1 px-1 text-muted fw-bold'>{old}</span>
                                <i class='o-mail-Message-trackingSeparator fa fa-long-arrow-right mx-1 text-600'/>
                                <span class='o-mail-Message-trackingNew me-1 fw-bold text-info'>{new}</span>
                                <span class='o-mail-Message-trackingField ms-1 fst-italic text-muted'>({diff})</span>
                            </li>""").format(old=old_value[diff_key], new=new_value[diff_key], diff=diff_key)
                        for diff_key in diff_keys]
                    )
                )
                kwargs['body'] = body
                super()._message_log(**kwargs)

    def _message_log(self, **kwargs):
        # OVERRIDE _message_log
        # We only log the modification of the tracked fields if the tax is
        # currently used in transactions. We remove the `repartition_lines_str`
        # from tracked value to avoid having it logged twice (once in the raw
        # string format and one in the nice formatted way thanks to
        # `_message_log_repartition_lines`)

        self.ensure_one()

        if self.is_used:
            repartition_line_str_field_id = self.env['ir.model.fields']._get('account.tax', 'repartition_lines_str').id
            for tracked_value_id in kwargs['tracking_value_ids']:
                if tracked_value_id[2]['field_id'] == repartition_line_str_field_id:
                    kwargs['tracking_value_ids'].remove(tracked_value_id)
                    self._message_log_repartition_lines(tracked_value_id[2]['old_value_char'], tracked_value_id[2]['new_value_char'])

            return super()._message_log(**kwargs)

    @api.depends('company_id')
    def _compute_invoice_repartition_line_ids(self):
        for tax in self:
            if not tax.invoice_repartition_line_ids:
                tax.invoice_repartition_line_ids = [
                    Command.create({'document_type': 'invoice', 'repartition_type': 'base', 'tag_ids': []}),
                    Command.create({'document_type': 'invoice', 'repartition_type': 'tax', 'tag_ids': []}),
                ]

    @api.depends('company_id')
    def _compute_refund_repartition_line_ids(self):
        for tax in self:
            if not tax.refund_repartition_line_ids:
                tax.refund_repartition_line_ids = [
                    Command.create({'document_type': 'refund', 'repartition_type': 'base', 'tag_ids': []}),
                    Command.create({'document_type': 'refund', 'repartition_type': 'tax', 'tag_ids': []}),
                ]

    @staticmethod
    def _parse_name_search(name):
        """
        Parse the name to search the taxes faster.
        Technical:  0EUM      => 0%E%U%M
                    21M       => 2%1%M%   where the % represents 0, 1 or multiple characters in a SQL 'LIKE' search.
                    21" M"    => 2%1% M%
                    21" M"co  => 2%1% M%c%o%
        Examples:   0EUM      => VAT 0% EU M.
                    21M       => 21% M , 21% EU M, 21% M.Cocont and 21% EX M.
                    21" M"    => 21% M and 21% M.Cocont.
                    21" M"co  => 21% M.Cocont.
        """
        regex = r"(\"[^\"]*\")"
        list_name = re.split(regex, name)
        for i, name in enumerate(list_name.copy()):
            if not name:
                continue
            if re.search(regex, name):
                list_name[i] = "%" + name.replace("%", "_").replace("\"", "") + "%"
            else:
                list_name[i] = '%'.join(re.sub(r"\W+", "", name))
        return ''.join(list_name)

    @api.model
    def _name_search(self, name, domain=None, operator='ilike', limit=None, order=None):
        if operator in ("ilike", "like"):
            name = AccountTax._parse_name_search(name)
        return super()._name_search(name, domain, operator, limit, order)

    def _search_name(self, operator, value):
        if operator not in ("ilike", "like") or not isinstance(value, str):
            return [('name', operator, value)]
        return [('name', operator, AccountTax._parse_name_search(value))]

    def _check_repartition_lines(self, lines):
        self.ensure_one()

        base_line = lines.filtered(lambda x: x.repartition_type == 'base')
        if len(base_line) != 1:
            raise ValidationError(_("Invoice and credit note distribution should each contain exactly one line for the base."))

    @api.constrains('invoice_repartition_line_ids', 'refund_repartition_line_ids', 'repartition_line_ids')
    def _validate_repartition_lines(self):
        for record in self:
            # if the tax is an aggregation of its sub-taxes (group) it can have no repartition lines
            if record.amount_type == 'group' and \
                    not record.invoice_repartition_line_ids and \
                    not record.refund_repartition_line_ids:
                continue

            invoice_repartition_line_ids = record.invoice_repartition_line_ids.sorted(lambda l: (l.sequence, l.id))
            refund_repartition_line_ids = record.refund_repartition_line_ids.sorted(lambda l: (l.sequence, l.id))
            record._check_repartition_lines(invoice_repartition_line_ids)
            record._check_repartition_lines(refund_repartition_line_ids)

            if len(invoice_repartition_line_ids) != len(refund_repartition_line_ids):
                raise ValidationError(_("Invoice and credit note distribution should have the same number of lines."))

            if not invoice_repartition_line_ids.filtered(lambda x: x.repartition_type == 'tax') or \
                    not refund_repartition_line_ids.filtered(lambda x: x.repartition_type == 'tax'):
                raise ValidationError(_("Invoice and credit note repartition should have at least one tax repartition line."))

            index = 0
            while index < len(invoice_repartition_line_ids):
                inv_rep_ln = invoice_repartition_line_ids[index]
                ref_rep_ln = refund_repartition_line_ids[index]
                if inv_rep_ln.repartition_type != ref_rep_ln.repartition_type or inv_rep_ln.factor_percent != ref_rep_ln.factor_percent:
                    raise ValidationError(_("Invoice and credit note distribution should match (same percentages, in the same order)."))
                index += 1

    @api.constrains('children_tax_ids', 'type_tax_use')
    def _check_children_scope(self):
        for tax in self:
            if not tax._check_m2m_recursion('children_tax_ids'):
                raise ValidationError(_("Recursion found for tax %r.", tax.name))
            if any(child.type_tax_use not in ('none', tax.type_tax_use) or child.tax_scope != tax.tax_scope for child in tax.children_tax_ids):
                raise ValidationError(_('The application scope of taxes in a group must be either the same as the group or left empty.'))

    @api.constrains('company_id')
    def _check_company_consistency(self):
        for company, taxes in groupby(self, lambda tax: tax.company_id):
            if self.env['account.move.line'].search([
                '|',
                ('tax_line_id', 'in', [tax.id for tax in taxes]),
                ('tax_ids', 'in', [tax.id for tax in taxes]),
                '!', ('company_id', 'child_of', company.id)
            ], limit=1):
                raise UserError(_("You can't change the company of your tax since there are some journal items linked to it."))

    def _sanitize_vals(self, vals):
        """Normalize the create/write values."""
        sanitized = vals.copy()
        # Allow to provide invoice_repartition_line_ids and refund_repartition_line_ids by dispatching them
        # correctly in the repartition_line_ids
        if 'repartition_line_ids' in sanitized and (
            'invoice_repartition_line_ids' in sanitized
            or 'refund_repartition_line_ids' in sanitized
        ):
            del sanitized['repartition_line_ids']
        for doc_type in ('invoice', 'refund'):
            fname = f"{doc_type}_repartition_line_ids"
            if fname in sanitized:
                repartition = sanitized.setdefault('repartition_line_ids', [])
                for command_vals in sanitized.pop(fname):
                    if command_vals[0] == Command.CREATE:
                        repartition.append(Command.create({'document_type': doc_type, **command_vals[2]}))
                    elif command_vals[0] == Command.UPDATE:
                        repartition.append(Command.update(command_vals[1], {'document_type': doc_type, **command_vals[2]}))
                    else:
                        repartition.append(command_vals)
                sanitized[fname] = []
        return sanitized

    @api.model_create_multi
    def create(self, vals_list):
        context = clean_context(self.env.context)
        context.update({
            'mail_create_nosubscribe': True, # At create or message_post, do not subscribe the current user to the record thread
            'mail_auto_subscribe_no_notify': True, # Do no notify users set as followers of the mail thread
            'mail_create_nolog': True, # At create, do not log the automatic ‘<Document> created’ message
        })
        taxes = super(AccountTax, self.with_context(context)).create([self._sanitize_vals(vals) for vals in vals_list])
        return taxes

    def write(self, vals):
        return super().write(self._sanitize_vals(vals))

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        default = dict(default or {})
        if 'name' not in default:
            default['name'] = _("%s (Copy)", self.name)
        return super(AccountTax, self).copy(default=default)

    @api.depends('type_tax_use', 'tax_scope')
    @api.depends_context('append_type_to_tax_name')
    def _compute_display_name(self):
        type_tax_use = dict(self._fields['type_tax_use']._description_selection(self.env))
        tax_scope = dict(self._fields['tax_scope']._description_selection(self.env))
        for record in self:
            name = record.name
            if self._context.get('append_type_to_tax_name'):
                name += ' (%s)' % type_tax_use.get(record.type_tax_use)
            if record.tax_scope:
                name += ' (%s)' % tax_scope.get(record.tax_scope)
            if len(self.env.companies) > 1 and self.env.context.get('params', {}).get('model') == 'product.template':
                name += ' (%s)' % record.company_id.display_name
            if record.country_id != record.company_id.account_fiscal_country_id:
                name += ' (%s)' % record.country_code
            record.display_name = name

    @api.onchange('amount')
    def onchange_amount(self):
        if self.amount_type in ('percent', 'division') and self.amount != 0.0 and not self.invoice_label:
            self.invoice_label = "{0:.4g}%".format(self.amount)

    @api.onchange('amount_type')
    def onchange_amount_type(self):
        if self.amount_type != 'group':
            self.children_tax_ids = [(5,)]
        if self.amount_type == 'group':
            self.invoice_label = None

    @api.onchange('price_include')
    def onchange_price_include(self):
        if self.price_include:
            self.include_base_amount = True

    @api.model
    def _prepare_taxes_batches(self, tax_values_list):
        batches = []

        def batch_key(tax):
            return tax.amount_type, tax_values['price_include']

        def append_batch(batch):
            batch['taxes'] = list(reversed(batch['taxes']))
            batches.append(batch)

        current_batch = None
        is_base_affected = None
        for tax_values in reversed(tax_values_list):
            tax = tax_values['tax']

            if current_batch is not None:
                force_new_batch = (tax.include_base_amount and is_base_affected)
                if current_batch['key'] != batch_key(tax) or force_new_batch:
                    append_batch(current_batch)
                    current_batch = None

            if current_batch is None:
                current_batch = {
                    'key': batch_key(tax),
                    'taxes': [],
                    'amount_type': tax.amount_type,
                    'include_base_amount': tax.include_base_amount,
                    'price_include': tax_values['price_include'],
                }

            is_base_affected = tax.is_base_affected
            current_batch['taxes'].append(tax_values)

        if current_batch is not None:
            append_batch(current_batch)

        return batches

    @api.model
    def _ascending_process_fixed_taxes_batch(self, batch, base, precision_rounding, extra_computation_values, fixed_multiplicator=1):
        if batch['amount_type'] == 'fixed':
            batch['computed'] = True
            quantity = abs(extra_computation_values['quantity'])
            for tax_values in batch['taxes']:
                tax_values['tax_amount'] = quantity * tax_values['tax'].amount * abs(fixed_multiplicator)
                tax_values['tax_amount_factorized'] = float_round(
                    tax_values['tax_amount'] * tax_values['factor'],
                    precision_rounding=precision_rounding,
                )

    @api.model
    def _descending_process_price_included_taxes_batch(self, batch, base, precision_rounding, extra_computation_values):
        tax_values_list = batch['taxes']
        amount_type = batch['amount_type']
        price_include = batch['price_include']

        if price_include:
            if amount_type == 'percent':
                batch['computed'] = True
                total_percent = sum(
                    tax_values['tax'].amount * tax_values['factor']
                    for tax_values in tax_values_list
                ) / 100.0
                computation_base = base / (1 + total_percent)
                for tax_values in tax_values_list:
                    tax_values['tax_amount'] = computation_base * tax_values['tax'].amount / 100.0
                    tax_values['tax_amount_factorized'] = float_round(
                        tax_values['tax_amount'] * tax_values['factor'],
                        precision_rounding=precision_rounding,
                    )

                batch_base = base - sum(tax_values['tax_amount_factorized'] for tax_values in tax_values_list)
                for tax_values in tax_values_list:
                    tax_values['base'] = tax_values['display_base'] = batch_base

            elif amount_type == 'division':
                batch['computed'] = True

                for tax_values in tax_values_list:
                    tax = tax_values['tax']
                    not_factorized_base = base * (1 - (tax_values['tax'].amount * tax_values['factor'] / 100.0))
                    tax_values['tax_amount'] = base - not_factorized_base
                    tax_values['tax_amount_factorized'] = float_round(
                        tax_values['tax_amount'] * tax_values['factor'],
                        precision_rounding=precision_rounding,
                    )
                    tax_values['display_base'] = base
                    tax_values['base'] = base - tax_values['tax_amount_factorized']

            elif amount_type == 'fixed':
                batch['computed'] = True
                batch_base = base - sum(tax_values['tax_amount_factorized'] for tax_values in tax_values_list)
                for tax_values in tax_values_list:
                    tax_values['base'] = tax_values['display_base'] = batch_base

    @api.model
    def _ascending_process_taxes_batch(self, batch, base, precision_rounding, extra_computation_values):
        tax_values_list = batch['taxes']
        amount_type = tax_values_list[0]['tax'].amount_type
        price_include = batch['price_include']

        if not price_include:

            if amount_type == 'percent':
                batch['computed'] = True
                for tax_values in tax_values_list:
                    tax_values['tax_amount'] = base * tax_values['tax'].amount / 100.0
                    tax_values['tax_amount_factorized'] = float_round(
                        tax_values['tax_amount'] * tax_values['factor'],
                        precision_rounding=precision_rounding,
                    )
                    tax_values['base'] = tax_values['display_base'] = base

            elif amount_type == 'division':
                batch['computed'] = True
                for tax_values in tax_values_list:
                    base_tax_included = base / (1 - (tax_values['tax'].amount / 100.0))
                    tax_values['tax_amount'] = base_tax_included - base
                    tax_values['tax_amount_factorized'] = float_round(
                        tax_values['tax_amount'] * tax_values['factor'],
                        precision_rounding=precision_rounding,
                    )
                    tax_values['base'] = tax_values['display_base'] = base

            elif amount_type == 'fixed':
                batch['computed'] = True
                quantity = abs(extra_computation_values['quantity'])
                for tax_values in tax_values_list:
                    tax_values['tax_amount'] = quantity * tax_values['tax'].amount
                    tax_values['tax_amount_factorized'] = float_round(
                        tax_values['tax_amount'] * tax_values['factor'],
                        precision_rounding=precision_rounding,
                    )
                    tax_values['base'] = tax_values['display_base'] = base

    @api.model
    def _prepare_tax_repartition_line_results(self, tax_values, currency, precision_rounding):
        repartition_line_amounts = [
            float_round(tax_values['tax_amount'] * line.factor, precision_rounding=precision_rounding)
            for line in tax_values['repartition_lines']
        ]
        total_rounding_error = float_round(
            tax_values['tax_amount_factorized'] - sum(repartition_line_amounts),
            precision_rounding=precision_rounding,
        )
        nber_rounding_steps = int(abs(total_rounding_error / currency.rounding))
        rounding_error = float_round(
            total_rounding_error / nber_rounding_steps if nber_rounding_steps else 0.0,
            precision_rounding=precision_rounding,
        )

        tax_repartition_values_list = []
        for repartition_line, line_amount in zip(tax_values['repartition_lines'], repartition_line_amounts):

            if nber_rounding_steps:
                line_amount += rounding_error
                nber_rounding_steps -= 1

            tax_repartition_values_list.append({
                'tax_amount': line_amount,
                'repartition_line': repartition_line,
            })
        return tax_repartition_values_list

    def flatten_taxes_hierarchy(self, create_map=False):
        # Flattens the taxes contained in this recordset, returning all the
        # children at the bottom of the hierarchy, in a recordset, ordered by sequence.
        #   Eg. considering letters as taxes and alphabetic order as sequence :
        #   [G, B([A, D, F]), E, C] will be computed as [A, D, F, C, E, G]
        # If create_map is True, an additional value is returned, a dictionary
        # mapping each child tax to its parent group
        all_taxes = self.env['account.tax']
        groups_map = {}
        for tax in self.sorted(key=lambda r: r.sequence):
            if tax.amount_type == 'group':
                flattened_children = tax.children_tax_ids.flatten_taxes_hierarchy()
                all_taxes += flattened_children
                for flat_child in flattened_children:
                    groups_map[flat_child] = tax
            else:
                all_taxes += tax

        if create_map:
            return all_taxes, groups_map

        return all_taxes

    def get_tax_tags(self, is_refund, repartition_type):
        document_type = 'refund' if is_refund else 'invoice'
        return self.repartition_line_ids\
            .filtered(lambda x: x.repartition_type == repartition_type and x.document_type == document_type)\
            .mapped('tag_ids')

    @api.model
    def _prepare_base_line_tax_details(self, base_line, company, fixed_multiplicator=1, need_extra_precision=None):
        currency = base_line['currency'] or company.currency_id

        # Flatten the taxes to handle the group of taxes.
        taxes = base_line['taxes']._origin
        taxes, groups_map = taxes.flatten_taxes_hierarchy(create_map=True)

        # Currency precision.
        precision_rounding = currency.rounding
        if need_extra_precision is None:
            need_extra_precision = company.tax_calculation_rounding_method == 'round_globally'
        if need_extra_precision:
            precision_rounding *= 1e-5

        # Initial base amount.
        # All computation starts with a rounded amount because everything ends up in moneraty fields after all.
        price_unit = base_line['price_unit'] * (1 - (base_line['discount'] / 100.0))
        quantity = base_line['quantity']
        base = currency.round(price_unit * quantity)
        rate = base_line['rate'] or 1.0
        is_refund = base_line['is_refund']

        sign = 1
        if currency.is_zero(base):
            sign = -1 if fixed_multiplicator < 0 else 1
        elif base < 0:
            sign = -1
            base = -base

        # Convert each tax into a dictionary.
        if is_refund:
            repartition_lines_field = 'refund_repartition_line_ids'
        else:
            repartition_lines_field = 'invoice_repartition_line_ids'

        handle_price_include = base_line['handle_price_include']
        force_price_include = base_line['extra_context'].get('force_price_include')

        tax_values_list = []
        for tax in taxes:
            tax_values = {
                'tax': tax,
                'price_include': handle_price_include and (tax.price_include or force_price_include),
                'repartition_lines': tax[repartition_lines_field].filtered(lambda x: x.repartition_type == "tax"),
            }
            tax_values['factor'] = sum(tax_values['repartition_lines'].mapped('factor'))
            tax_values_list.append(tax_values)

        # Prepare computation of python taxes (see the 'account_tax_python' module).
        product = base_line['product']
        partner = base_line['partner']
        extra_computation_values = {
            'price_unit': price_unit,
            'quantity': quantity,
            'product': product,
            'partner': partner,
            'fixed_multiplicator': fixed_multiplicator,
            'company': company,
        }

        # Group the taxes by batch of computation.
        descending_batches = self._prepare_taxes_batches(tax_values_list)
        ascending_batches = list(reversed(descending_batches))

        # First ascending computation for fixed tax.
        # In Belgium, we could have a price-excluded tax affecting the base of a price-included tax.
        # In that case, we need to compute the fix amount before the descending computation.
        extra_base = 0.0
        for batch in ascending_batches:
            batch['extra_base'] = extra_base
            self._ascending_process_fixed_taxes_batch(
                batch,
                base,
                precision_rounding,
                extra_computation_values,
                fixed_multiplicator=fixed_multiplicator,
            )
            if batch.get('computed'):
                batch.pop('computed')
                if batch['include_base_amount']:
                    extra_base += sum(tax_values['tax_amount_factorized'] for tax_values in batch['taxes'])

        # First descending computation to compute price_included values and find the total_excluded amount.
        for batch in descending_batches:
            self._descending_process_price_included_taxes_batch(
                batch,
                base + batch['extra_base'],
                precision_rounding,
                extra_computation_values,
            )
            if batch.get('computed'):
                base -= sum(tax_values['tax_amount_factorized'] for tax_values in batch['taxes'])

        first_base = base

        # Second ascending computation to compute the missing values for price-excluded taxes.
        # Build the final results.
        tax_details_list = []
        for i, batch in enumerate(ascending_batches):
            is_computed = batch.get('computed')
            if is_computed:
                # All already computed batches are considered as include in price. It's the trade-off
                # when dealing with both price-included and price-excluded taxes.
                base += sum(tax_values['tax_amount_factorized'] for tax_values in batch['taxes'])
            else:
                self._ascending_process_taxes_batch(
                    batch,
                    base,
                    precision_rounding,
                    extra_computation_values,
                )

            subsequent_taxes = self.env['account.tax']
            subsequent_tags = self.env['account.account.tag']
            if batch['include_base_amount']:

                # Price-included taxes are already accounted at this point.
                if not is_computed:
                    base += sum(tax_values['tax_amount_factorized'] for tax_values in batch['taxes'])

                for next_batch in ascending_batches[i + 1:]:
                    for next_tax_values in next_batch['taxes']:
                        subsequent_taxes |= next_tax_values['tax']

            for tax_values in batch['taxes']:
                tax = tax_values['tax']
                tax_values.update({
                    'name': tax.with_context(lang=partner.lang).name if partner else tax.name,
                    'group': groups_map.get(tax),
                    'taxes': subsequent_taxes,
                    'price_include': batch['price_include'],
                })
                for field_to_sign in ('tax_amount', 'tax_amount_factorized', 'base', 'display_base'):
                    tax_values[field_to_sign] *= sign

                tax_details_list.append(tax_values)

        return {
            'base': sign * first_base,
            'precision_rounding': precision_rounding,
            'repartition_lines_field': repartition_lines_field,
            'tax_details_list': tax_details_list,
        }

    @api.model
    def _split_base_lines_tax_details_per_repartition_lines(self, to_process, company, include_caba_tags=False):
        results = []
        for base_line, tax_details_results in to_process:
            is_refund = base_line['is_refund']
            currency = base_line['currency'] or company.currency_id
            product = base_line['product']
            rate = base_line['rate'] or 1.0

            tax_details_list = tax_details_results['tax_details_list']
            tax_details_list = tax_details_results['tax_details_list']
            base = tax_details_results['base']
            precision_rounding = tax_details_results['precision_rounding']
            repartition_lines_field = tax_details_results['repartition_lines_field']

            total_included = total_void = total_excluded = base
            base_taxes_for_tags = self.env['account.tax']
            repartition_tax_details_list = []
            for tax_values in tax_details_list:
                tax = tax_values['tax']
                subsequent_taxes = tax_values['taxes']

                # Compute the subsequent tags.
                taxes_for_subsequent_tags = subsequent_taxes
                if not include_caba_tags:
                    taxes_for_subsequent_tags = subsequent_taxes.filtered(lambda x: x.tax_exigibility != 'on_payment')
                subsequent_tags = taxes_for_subsequent_tags.get_tax_tags(is_refund, 'base')

                # Dispatch the amount onto the repartition lines.
                # Take care of rounding errors: the sum of each sub-amount must be exactly equal to the tax amount.
                repartition_line_amounts = [
                    float_round(tax_values['tax_amount'] * line.factor, precision_rounding=precision_rounding)
                    for line in tax_values['repartition_lines']
                ]
                total_rounding_error = float_round(
                    tax_values['tax_amount_factorized'] - sum(repartition_line_amounts),
                    precision_rounding=precision_rounding,
                )
                nber_rounding_steps = int(abs(total_rounding_error / currency.rounding))
                rounding_error = float_round(
                    total_rounding_error / nber_rounding_steps if nber_rounding_steps else 0.0,
                    precision_rounding=precision_rounding,
                )

                # Create the result for each repartition lines.
                for repartition_line, line_amount in zip(tax_values['repartition_lines'], repartition_line_amounts):

                    # The error is smoothly dispatched on repartition lines.
                    # If you have 5 repartition lines and 0.03 to dispatch, three of them will take 0.01 instead of
                    # only one getting 0.03.
                    if nber_rounding_steps:
                        line_amount += rounding_error
                        nber_rounding_steps -= 1

                    if not include_caba_tags and tax.tax_exigibility == 'on_payment':
                        repartition_line_tags = self.env['account.account.tag']
                    else:
                        repartition_line_tags = repartition_line.tag_ids

                    repartition_tax_details_list.append({
                        'tax': tax,
                        'name': tax_values['name'],
                        'tax_amount_currency': line_amount,
                        'tax_amount': line_amount / rate,
                        'base_amount_currency': tax_values['base'],
                        'base_amount': tax_values['base'] / rate,
                        'display_base_amount_currency': tax_values['display_base'],
                        'display_base_amount': tax_values['display_base'] / rate,
                        'account': repartition_line._get_aml_target_tax_account(force_caba_exigibility=include_caba_tags),
                        'tax_repartition_line': repartition_line,
                        'group': tax_values['group'] or self.env['account.tax'],
                        'tags': repartition_line_tags + subsequent_tags,
                        'taxes': subsequent_taxes,
                    })

                    if not repartition_line.account_id:
                        total_void += line_amount
                    total_included += line_amount

                if include_caba_tags or tax.tax_exigibility != 'on_payment':
                    base_taxes_for_tags |= tax

            base_rep_lines = base_taxes_for_tags \
                .mapped(repartition_lines_field) \
                .filtered(lambda x: x.repartition_type == 'base')

            tax_details_results.update({
                'base_tags': base_rep_lines.tag_ids + product.account_tag_ids,
                'taxes': repartition_tax_details_list,
                'total_excluded': currency.round(total_excluded),
                'total_included': currency.round(total_included),
                'total_void': currency.round(total_void),
            })

    @api.model
    def _round_base_lines_tax_details(self, to_process, company, tax_lines=None):
        amount_per_grouping_key = defaultdict(lambda: {
            'base_amount_currency': 0.0,
            'tax_amount_currency': 0.0,
            'tax_details_list': [],
        })

        # Map the tax lines.
        tax_line_mapping = {}
        for tax_line in tax_lines or []:
            grouping_key = frozendict(self._get_generation_dict_from_tax_line(tax_line))
            tax_line_mapping[grouping_key] = tax_line

        # Aggregate the tax details according the grouping key.
        for base_line, tax_details_results in to_process:
            currency = base_line['currency'] or company.currency_id
            for tax_values in tax_details_results['taxes']:
                grouping_key = frozendict(self._get_generation_dict_from_base_line(base_line, tax_values))
                amounts = amount_per_grouping_key[grouping_key]
                amounts['base_amount_currency'] += tax_values['base_amount_currency']
                amounts['tax_amount_currency'] += tax_values['tax_amount_currency']
                amounts['tax_details_list'].append(tax_values)

        # Round and dispatch the error.
        for grouping_key, amounts in amount_per_grouping_key.items():

            if grouping_key in tax_line_mapping:
                amounts['tax_amount_currency'] = tax_line_mapping[grouping_key]['tax_amount']

            for key_to_fix in ('base_amount_currency', 'tax_amount_currency'):
                total_value = 0.0
                for tax_values in amounts['tax_details_list']:
                    tax_values[key_to_fix] = currency.round(tax_values[key_to_fix])
                    total_value += tax_values[key_to_fix]

                total_rounding_error = currency.round(amounts[key_to_fix]) - total_value
                nber_rounding_steps = int(abs(total_rounding_error / currency.rounding))
                rounding_error = currency.round(total_rounding_error / nber_rounding_steps if nber_rounding_steps else 0.0)

                for tax_values in amounts['tax_details_list']:
                    if not nber_rounding_steps:
                        break

                    tax_values[key_to_fix] += rounding_error
                    nber_rounding_steps -= 1

    def compute_all(self, price_unit, currency=None, quantity=1.0, product=None, partner=None, is_refund=False, handle_price_include=True, include_caba_tags=False, fixed_multiplicator=1):
        """Compute all information required to apply taxes (in self + their children in case of a tax group).
        We consider the sequence of the parent for group of taxes.
            Eg. considering letters as taxes and alphabetic order as sequence :
            [G, B([A, D, F]), E, C] will be computed as [A, D, F, C, E, G]



        :param price_unit: The unit price of the line to compute taxes on.
        :param currency: The optional currency in which the price_unit is expressed.
        :param quantity: The optional quantity of the product to compute taxes on.
        :param product: The optional product to compute taxes on.
            Used to get the tags to apply on the lines.
        :param partner: The optional partner compute taxes on.
            Used to retrieve the lang to build strings and for potential extensions.
        :param is_refund: The optional boolean indicating if this is a refund.
        :param handle_price_include: Used when we need to ignore all tax included in price. If False, it means the
            amount passed to this method will be considered as the base of all computations.
        :param include_caba_tags: The optional boolean indicating if CABA tags need to be taken into account.
        :param fixed_multiplicator: The amount to multiply fixed amount taxes by.
        :return: {
            'total_excluded': 0.0,    # Total without taxes
            'total_included': 0.0,    # Total with taxes
            'total_void'    : 0.0,    # Total with those taxes, that don't have an account set
            'base_tags: : list<int>,  # Tags to apply on the base line
            'taxes': [{               # One dict for each tax in self and their children
                'id': int,
                'name': str,
                'amount': float,
                'base': float,
                'sequence': int,
                'account_id': int,
                'refund_account_id': int,
                'analytic': bool,
                'price_include': bool,
                'tax_exigibility': str,
                'tax_repartition_line_id': int,
                'group': recordset,
                'tag_ids': list<int>,
                'tax_ids': list<int>,
            }],
        } """
        if not self:
            company = self.env.company
        else:
            company = self[0].company_id._accessible_branches()[:1]

        # Compute tax details for a single line.
        currency = currency or company.currency_id
        base_line = self._convert_to_tax_base_line_dict(
            None,
            partner=partner,
            currency=currency,
            product=product,
            taxes=self,
            price_unit=price_unit,
            quantity=quantity,
            is_refund=is_refund,
            handle_price_include=handle_price_include,
            extra_context={'force_price_include': self._context.get('force_price_include')},
        )
        product = base_line['product']
        kwargs = {'need_extra_precision': True} if self._context.get('round') else {}
        tax_details_results = self._prepare_base_line_tax_details(
            base_line,
            company,
            fixed_multiplicator=fixed_multiplicator,
            **kwargs,
        )
        self._split_base_lines_tax_details_per_repartition_lines(
            [(base_line, tax_details_results)],
            company,
            include_caba_tags=include_caba_tags,
        )

        # Convert to the 'old' compute_all api.
        results = {
            k: v
            for k, v in tax_details_results.items()
            if k in ('base_tags', 'taxes', 'total_excluded', 'total_included', 'total_void')
        }
        base_tags = results.pop('base_tags')
        results['base_tags'] = base_tags.ids

        for tax_values in results['taxes']:
            tax = tax_values.pop('tax')
            tax_rep = tax_values.pop('tax_repartition_line')
            account = tax_values.pop('account')
            tags = tax_values.pop('tags')
            taxes = tax_values.pop('taxes')
            tax_values.update({
                'id': tax.id,
                'name': tax_values['name'],
                'sequence': tax.sequence,
                'account_id': account.id,
                'analytic': tax.analytic,
                'tax_exigibility': tax.tax_exigibility,
                'tax_repartition_line_id': tax_rep.id,
                'use_in_tax_closing': tax_rep.use_in_tax_closing,
                'tag_ids': tags.ids,
                'tax_ids': taxes.ids,
                'base': tax_values['base_amount_currency'],
                'amount': tax_values['tax_amount_currency'],
            })

        return results

    @api.model
    def _convert_to_tax_base_line_dict(
            self, base_line,
            partner=None, currency=None, product=None, taxes=None, price_unit=None, quantity=None,
            discount=None, account=None, analytic_distribution=None, price_subtotal=None,
            is_refund=False, rate=None,
            handle_price_include=True,
            extra_context=None,
    ):
        if product and product._name == 'product.template':
            product = product.product_variant_id
        return {
            'record': base_line,
            'partner': partner or self.env['res.partner'],
            'currency': currency or self.env['res.currency'],
            'product': product or self.env['product.product'],
            'taxes': taxes or self.env['account.tax'],
            'price_unit': price_unit or 0.0,
            'quantity': quantity or 0.0,
            'discount': discount or 0.0,
            'account': account or self.env['account.account'],
            'analytic_distribution': analytic_distribution,
            'price_subtotal': price_subtotal or 0.0,
            'is_refund': is_refund,
            'rate': rate or 1.0,
            'handle_price_include': handle_price_include,
            'extra_context': extra_context or {},
        }

    @api.model
    def _convert_to_tax_line_dict(
            self, tax_line,
            partner=None, currency=None, taxes=None, tax_tags=None, tax_repartition_line=None,
            group_tax=None, account=None, analytic_distribution=None, tax_amount=None,
    ):
        return {
            'record': tax_line,
            'partner': partner or self.env['res.partner'],
            'currency': currency or self.env['res.currency'],
            'taxes': taxes or self.env['account.tax'],
            'tax_tags': tax_tags or self.env['account.account.tag'],
            'tax_repartition_line': tax_repartition_line or self.env['account.tax.repartition.line'],
            'group_tax': group_tax or self.env['account.tax'],
            'account': account or self.env['account.account'],
            'analytic_distribution': analytic_distribution,
            'tax_amount': tax_amount or 0.0,
        }

    @api.model
    def _get_generation_dict_from_base_line(self, line_vals, tax_vals, force_caba_exigibility=False):
        """ Take a tax results returned by the taxes computation method and return a dictionary representing the way
        the tax amounts will be grouped together. To do so, the dictionary will be converted into a string key.
        Then, the existing tax lines sharing the same key will be updated and the missing ones will be created.

        :param line_vals:   A python dict returned by '_convert_to_tax_base_line_dict'.
        :param tax_vals:    A python dict returned by 'compute_all' under the 'taxes' key.
        :return:            A python dict.
        """
        tax_repartition_line = tax_vals['tax_repartition_line']
        tax = tax_repartition_line.tax_id
        tax_account = tax_repartition_line._get_aml_target_tax_account(force_caba_exigibility=force_caba_exigibility) or line_vals['account']
        return {
            'account_id': tax_account.id,
            'currency_id': line_vals['currency'].id,
            'partner_id': line_vals['partner'].id,
            'tax_repartition_line_id': tax_repartition_line.id,
            'tax_ids': [Command.set(tax_vals['taxes'].ids)],
            'tax_tag_ids': [Command.set(tax_vals['tags'].ids)],
            'tax_id': tax_vals['group'].id or tax.id,
            'analytic_distribution': line_vals['analytic_distribution'] if tax.analytic else {},
        }

    @api.model
    def _get_generation_dict_from_tax_line(self, line_vals):
        """ Turn the values corresponding to a tax line and convert it into a dictionary. The dictionary will be
        converted into a string key. This allows updating the existing tax lines instead of creating new ones
        everytime.

        :param line_vals:   A python dict returned by '_convert_to_tax_line_dict'.
        :return:            A python dict representing the grouping key used to update an existing tax line.
        """
        tax = line_vals['tax_repartition_line'].tax_id
        return {
            'account_id': line_vals['account'].id,
            'currency_id': line_vals['currency'].id,
            'partner_id': line_vals['partner'].id,
            'tax_repartition_line_id': line_vals['tax_repartition_line'].id,
            'tax_ids': [Command.set(line_vals['taxes'].ids)],
            'tax_tag_ids': [Command.set(line_vals['tax_tags'].ids)],
            'tax_id': (line_vals['group_tax'] or tax).id,
            'analytic_distribution': line_vals['analytic_distribution'] if tax.analytic else {},
        }

    @api.model
    def _aggregate_taxes(self, to_process, company, filter_tax_values_to_apply=None, grouping_key_generator=None):

        def default_grouping_key_generator(base_line, tax_values):
            return {'tax': tax_values['tax_repartition_line'].tax_id}

        results = {
            'base_amount_currency': 0.0,
            'base_amount': 0.0,
            'display_base_amount_currency': 0.0,
            'display_base_amount': 0.0,
            'tax_amount_currency': 0.0,
            'tax_amount': 0.0,
            'tax_details': defaultdict(lambda: {
                'base_amount_currency': 0.0,
                'base_amount': 0.0,
                'display_base_amount_currency': 0.0,
                'display_base_amount': 0.0,
                'tax_amount_currency': 0.0,
                'tax_amount': 0.0,
                'group_tax_details': [],
                'records': set(),
            }),
            'tax_details_per_record': defaultdict(lambda: {
                'base_amount_currency': 0.0,
                'base_amount': 0.0,
                'display_base_amount_currency': 0.0,
                'display_base_amount': 0.0,
                'tax_amount_currency': 0.0,
                'tax_amount': 0.0,
                'tax_details': defaultdict(lambda: {
                    'base_amount_currency': 0.0,
                    'base_amount': 0.0,
                    'display_base_amount_currency': 0.0,
                    'display_base_amount': 0.0,
                    'tax_amount_currency': 0.0,
                    'tax_amount': 0.0,
                    'group_tax_details': [],
                    'records': set(),
                }),
            }),
        }

        if not grouping_key_generator:
            grouping_key_generator = default_grouping_key_generator

        currency = None
        comp_currency = company.currency_id

        for base_line, tax_details_results in to_process:
            record = base_line['record']
            currency = base_line['currency'] or comp_currency

            record_results = results['tax_details_per_record'][record]

            base_added = False
            base_grouping_key_added = set()
            for tax_values in tax_details_results['taxes']:
                grouping_key = frozendict(grouping_key_generator(base_line, tax_values))

                base_amount_currency = currency.round(tax_values['base_amount_currency'])
                base_amount = comp_currency.round(tax_values['base_amount'])
                display_base_amount_currency = currency.round(tax_values['display_base_amount_currency'])
                display_base_amount = comp_currency.round(tax_values['display_base_amount'])

                # 'global' base.
                if not base_added:
                    base_added = True
                    for sub_results in (results, record_results):
                        sub_results['base_amount_currency'] += base_amount_currency
                        sub_results['base_amount'] += base_amount
                        sub_results['display_base_amount_currency'] += display_base_amount_currency
                        sub_results['display_base_amount'] += display_base_amount

                # 'local' base.
                global_local_results = results['tax_details'][grouping_key]
                record_local_results = record_results['tax_details'][grouping_key]
                if grouping_key not in base_grouping_key_added:
                    base_grouping_key_added.add(grouping_key)
                    for sub_results in (global_local_results, record_local_results):
                        sub_results.update(grouping_key)
                        sub_results['base_amount_currency'] += base_amount_currency
                        sub_results['base_amount'] += base_amount
                        sub_results['display_base_amount_currency'] += display_base_amount_currency
                        sub_results['display_base_amount'] += display_base_amount
                        sub_results['records'].add(record)
                        sub_results['group_tax_details'].append(tax_values)

                # 'global'/'local' tax amount.
                for sub_results in (results, record_results, global_local_results, record_local_results):
                    sub_results['tax_amount_currency'] += tax_values['tax_amount_currency']
                    sub_results['tax_amount'] += tax_values['tax_amount']

            # Rounding of tax amounts for the line.
            if currency:
                for sub_results in [record_results] + list(record_results['tax_details'].values()):
                    sub_results['tax_amount_currency'] = currency.round(sub_results['tax_amount_currency'])
                    sub_results['tax_amount'] = comp_currency.round(sub_results['tax_amount'])

        # Rounding of tax amounts.
        if currency:
            for sub_results in [results] + list(results['tax_details'].values()):
                sub_results['tax_amount_currency'] = currency.round(sub_results['tax_amount_currency'])
                sub_results['tax_amount'] = comp_currency.round(sub_results['tax_amount'])

        return results

    @api.model
    def _compute_taxes(self, base_lines, company, tax_lines=None, include_caba_tags=False):
        """ Generic method to compute the taxes for different business models.

        :param base_lines: A list of python dictionaries created using the '_convert_to_tax_base_line_dict' method.
        :param company: The company to consider.
        :param tax_lines: A list of python dictionaries created using the '_convert_to_tax_line_dict' method.
        :param include_caba_tags: Manage tags for taxes being exigible on_payment.
        :return: A python dictionary containing:

            The complete diff on tax lines if 'tax_lines' is passed as parameter:
            * tax_lines_to_add:     To create new tax lines.
            * tax_lines_to_delete:  To track the tax lines that are no longer used.
            * tax_lines_to_update:  The values to update the existing tax lines.

            * base_lines_to_update: The values to update the existing base lines:
                * tax_tag_ids:          The tags related to taxes.
                * price_subtotal:       The amount without tax.
                * price_total:          The amount with taxes.

            * totals:               A mapping for each involved currency to:
                * amount_untaxed:       The base amount without tax.
                * amount_tax:           The total tax amount.
        """
        res = {
            'tax_lines_to_add': [],
            'tax_lines_to_delete': [],
            'tax_lines_to_update': [],
            'base_lines_to_update': [],
            'totals': defaultdict(lambda: {
                'amount_untaxed': 0.0,
                'amount_tax': 0.0,
            }),
        }

        # =========================================================================================
        # BASE LINES
        # For each base line, populate 'base_lines_to_update'.
        # Compute 'tax_base_amount'/'tax_amount' for each pair <base line, tax repartition line>
        # using the grouping key generated by the '_get_generation_dict_from_base_line' method.
        # =========================================================================================

        # Prepare the tax details for each line.
        to_process = []
        for base_line in base_lines:
            tax_details_results = self._prepare_base_line_tax_details(base_line, company)
            to_process.append((base_line, tax_details_results))

        # Split the tax details per repartition lines.
        self._split_base_lines_tax_details_per_repartition_lines(to_process, company, include_caba_tags=include_caba_tags)

        # Round according '_get_generation_dict_from_base_line' to avoid rounding issues when dealing with 'round_globally'.
        self._round_base_lines_tax_details(to_process, company, tax_lines=tax_lines)

        # Fill 'base_lines_to_update' and 'totals'.
        for base_line, tax_details_results in to_process:
            res['base_lines_to_update'].append((base_line, {
                'tax_tag_ids': [Command.set(tax_details_results['base_tags'].ids)],
                'price_subtotal': tax_details_results['total_excluded'],
                'price_total': tax_details_results['total_included'],
            }))

            currency = base_line['currency'] or company.currency_id
            res['totals'][currency]['amount_untaxed'] += tax_details_results['total_excluded']

        # =========================================================================================
        # TAX LINES
        # Map each existing tax lines using the grouping key generated by the
        # '_get_generation_dict_from_tax_line' method.
        # Since everything is indexed using the grouping key, we are now able to decide if
        # (1) we can reuse an existing tax line and update its amounts
        # (2) some tax lines are no longer used and can be dropped
        # (3) we need to create new tax lines
        # =========================================================================================

        # Track the existing tax lines using the grouping key.
        existing_tax_line_map = {}
        for line_vals in tax_lines or []:
            grouping_key = frozendict(self._get_generation_dict_from_tax_line(line_vals))

            # After a modification (e.g. changing the analytic account of the tax line), if two tax lines are sharing
            # the same key, keep only one.
            if grouping_key in existing_tax_line_map:
                res['tax_lines_to_delete'].append(line_vals)
            else:
                existing_tax_line_map[grouping_key] = line_vals

        def grouping_key_generator(base_line, tax_values):
            return self._get_generation_dict_from_base_line(base_line, tax_values, force_caba_exigibility=include_caba_tags)

        # Update/create the tax lines.
        global_tax_details = self._aggregate_taxes(to_process, company, grouping_key_generator=grouping_key_generator)

        for grouping_key, tax_values in global_tax_details['tax_details'].items():
            if tax_values['currency_id']:
                currency = self.env['res.currency'].browse(tax_values['currency_id'])
                tax_amount = currency.round(tax_values['tax_amount'])
                res['totals'][currency]['amount_tax'] += tax_amount

            if grouping_key in existing_tax_line_map:
                # Update an existing tax line.
                line_vals = existing_tax_line_map.pop(grouping_key)
                res['tax_lines_to_update'].append((line_vals, tax_values))
            else:
                # Create a new tax line.
                res['tax_lines_to_add'].append(tax_values)

        for line_vals in existing_tax_line_map.values():
            res['tax_lines_to_delete'].append(line_vals)

        return res

    @api.model
    def _prepare_tax_totals(self, base_lines, currency, company, tax_lines=None):
        """ Compute the tax totals details for the business documents.
        :param base_lines:                      A list of python dictionaries created using the '_convert_to_tax_base_line_dict' method.
        :param currency:                        The currency set on the business document.
        :param company:                         The company to consider.
        :param tax_lines:                       Optional list of python dictionaries created using the '_convert_to_tax_line_dict'
                                                method. If specified, the taxes will be recomputed using them instead of
                                                recomputing the taxes on the provided base lines.
        :return: A dictionary in the following form:
            {
                'amount_total':                 The total amount to be displayed on the document, including every total
                                                types.
                'amount_untaxed':               The untaxed amount to be displayed on the document.
                'formatted_amount_total':       Same as amount_total, but as a string formatted accordingly with
                                                partner's locale.
                'formatted_amount_untaxed':     Same as amount_untaxed, but as a string formatted accordingly with
                                                partner's locale.
                'groups_by_subtotals':          A dictionary formed liked {'subtotal': groups_data}
                                                Where total_type is a subtotal name defined on a tax group, or the
                                                default one: 'Untaxed Amount'.
                                                And groups_data is a list of dict in the following form:
                    {
                        'tax_group_name':                           The name of the tax groups this total is made for.
                        'tax_group_amount':                         The total tax amount in this tax group.
                        'tax_group_base_amount':                    The base amount for this tax group.
                        'formatted_tax_group_amount':               Same as tax_group_amount, but as a string formatted accordingly
                                                                    with partner's locale.
                        'formatted_tax_group_base_amount':          Same as tax_group_base_amount, but as a string formatted
                                                                    accordingly with partner's locale.
                        'tax_group_id':                             The id of the tax group corresponding to this dict.
                        'tax_group_base_amount_company_currency':   OPTIONAL: the base amount of the tax group expressed in
                                                                    the company currency when the parameter
                                                                    is_company_currency_requested is True
                        'tax_group_amount_company_currency':        OPTIONAL: the tax amount of the tax group expressed in
                                                                    the company currency when the parameter
                                                                    is_company_currency_requested is True
                    }
                'subtotals':                    A list of dictionaries in the following form, one for each subtotal in
                                                'groups_by_subtotals' keys.
                    {
                        'name':                             The name of the subtotal
                        'amount':                           The total amount for this subtotal, summing all the tax groups
                                                            belonging to preceding subtotals and the base amount
                        'formatted_amount':                 Same as amount, but as a string formatted accordingly with
                                                     b       partner's locale.
                        'amount_company_currency':          OPTIONAL: The total amount in company currency when the
                                                            parameter is_company_currency_requested is True
                    }
                'subtotals_order':              A list of keys of `groups_by_subtotals` defining the order in which it needs
                                                to be displayed
            }
        """
        comp_curr = company.currency_id

        # ==== Compute the taxes ====

        # Prepare the tax details for each line.
        to_process = []
        for base_line in base_lines:
            tax_details_results = self._prepare_base_line_tax_details(base_line, company)
            to_process.append((base_line, tax_details_results))

        # Split the tax details per repartition lines.
        self._split_base_lines_tax_details_per_repartition_lines(to_process, company)

        # Round according '_get_generation_dict_from_base_line' to avoid rounding issues when dealing with 'round_globally'.
        self._round_base_lines_tax_details(to_process, company, tax_lines=tax_lines)

        # Compute the untaxed amounts.
        amount_untaxed = 0.0
        amount_untaxed_currency = 0.0
        for base_line, tax_details_results in to_process:
            amount_untaxed += comp_curr.round(tax_details_results['total_excluded'] / base_line['rate'])
            amount_untaxed_currency += tax_details_results['total_excluded']

        def grouping_key_generator(base_line, tax_values):
            source_tax = tax_values['tax_repartition_line'].tax_id
            return {'tax_group': source_tax.tax_group_id}

        global_tax_details = self._aggregate_taxes(to_process, company, grouping_key_generator=grouping_key_generator)
        tax_group_details_list = sorted(
            global_tax_details['tax_details'].values(),
            key=lambda x: (x['tax_group'].sequence, x['tax_group'].id),
        )

        subtotal_order = {}
        encountered_base_amounts = {amount_untaxed_currency}
        groups_by_subtotal = defaultdict(list)
        for tax_detail in tax_group_details_list:
            tax_group = tax_detail['tax_group']
            subtotal_title = tax_group.preceding_subtotal or _("Untaxed Amount")
            sequence = tax_group.sequence

            # Handle a manual edition of tax lines.
            if tax_lines is not None:
                matched_tax_lines = [
                    x
                    for x in tax_lines
                    if x['tax_repartition_line'].tax_id.tax_group_id == tax_group
                ]
                if matched_tax_lines:
                    tax_detail['tax_amount_currency'] = sum(x['tax_amount'] for x in matched_tax_lines)

            # Manage order of subtotals.
            if subtotal_title not in subtotal_order:
                subtotal_order[subtotal_title] = sequence

            # Create the values for a single tax group.
            groups_by_subtotal[subtotal_title].append({
                'group_key': tax_group.id,
                'tax_group_id': tax_group.id,
                'tax_group_name': tax_group.name,
                'tax_group_amount': tax_detail['tax_amount_currency'],
                'tax_group_amount_company_currency': tax_detail['tax_amount'],
                'tax_group_base_amount': tax_detail['display_base_amount_currency'],
                'tax_group_base_amount_company_currency': tax_detail['display_base_amount'],
                'formatted_tax_group_amount': formatLang(self.env, tax_detail['tax_amount_currency'], currency_obj=currency),
                'formatted_tax_group_base_amount': formatLang(self.env, tax_detail['display_base_amount_currency'], currency_obj=currency),
            })
            encountered_base_amounts.add(tax_detail['display_base_amount_currency'])

        # Compute amounts.
        subtotals = []
        subtotals_order = sorted(subtotal_order.keys(), key=lambda k: subtotal_order[k])
        amount_total_currency = amount_untaxed_currency
        amount_total = amount_untaxed
        for subtotal_title in subtotals_order:
            subtotals.append({
                'name': subtotal_title,
                'amount': amount_total_currency,
                'amount_company_currency': amount_total,
                'formatted_amount': formatLang(self.env, amount_total_currency, currency_obj=currency),
            })
            amount_total_currency += sum(x['tax_group_amount'] for x in groups_by_subtotal[subtotal_title])
            amount_total += sum(x['tax_group_amount_company_currency'] for x in groups_by_subtotal[subtotal_title])

        return {
            'amount_untaxed': currency.round(amount_untaxed_currency),
            'amount_total': currency.round(amount_total_currency),
            'formatted_amount_total': formatLang(self.env, amount_total_currency, currency_obj=currency),
            'formatted_amount_untaxed': formatLang(self.env, amount_untaxed_currency, currency_obj=currency),
            'groups_by_subtotal': groups_by_subtotal,
            'subtotals': subtotals,
            'subtotals_order': subtotals_order,
            'display_tax_base': len(encountered_base_amounts) != 1 or len(groups_by_subtotal) > 1,
        }

    @api.model
    def _fix_tax_included_price(self, price, prod_taxes, line_taxes):
        """Subtract tax amount from price when corresponding "price included" taxes do not apply"""
        # FIXME get currency in param?
        prod_taxes = prod_taxes._origin
        line_taxes = line_taxes._origin
        incl_tax = prod_taxes.filtered(lambda tax: tax not in line_taxes and tax.price_include)
        if incl_tax:
            return incl_tax.compute_all(price)['total_excluded']
        return price

    @api.model
    def _fix_tax_included_price_company(self, price, prod_taxes, line_taxes, company_id):
        if company_id:
            #To keep the same behavior as in _compute_tax_id
            prod_taxes = prod_taxes.filtered(lambda tax: tax.company_id == company_id)
            line_taxes = line_taxes.filtered(lambda tax: tax.company_id == company_id)
        return self._fix_tax_included_price(price, prod_taxes, line_taxes)


class AccountTaxRepartitionLine(models.Model):
    _name = "account.tax.repartition.line"
    _description = "Tax Repartition Line"
    _order = 'document_type, repartition_type, sequence, id'
    _check_company_auto = True
    _check_company_domain = models.check_company_domain_parent_of

    factor_percent = fields.Float(
        string="%",
        default=100,
        required=True,
        help="Factor to apply on the account move lines generated from this distribution line, in percents",
    )
    factor = fields.Float(string="Factor Ratio", compute="_compute_factor", help="Factor to apply on the account move lines generated from this distribution line")
    repartition_type = fields.Selection(string="Based On", selection=[('base', 'Base'), ('tax', 'of tax')], required=True, default='tax', help="Base on which the factor will be applied.")
    document_type = fields.Selection(string="Related to", selection=[('invoice', 'Invoice'), ('refund', 'Refund')], required=True)
    account_id = fields.Many2one(string="Account",
        comodel_name='account.account',
        domain="[('deprecated', '=', False), ('account_type', 'not in', ('asset_receivable', 'liability_payable', 'off_balance'))]",
        check_company=True,
        help="Account on which to post the tax amount")
    tag_ids = fields.Many2many(string="Tax Grids", comodel_name='account.account.tag', domain=[('applicability', '=', 'taxes')], copy=True, ondelete='restrict')
    tax_id = fields.Many2one(comodel_name='account.tax', ondelete='cascade', check_company=True)
    company_id = fields.Many2one(string="Company", comodel_name='res.company', related="tax_id.company_id", store=True, help="The company this distribution line belongs to.")
    sequence = fields.Integer(string="Sequence", default=1,
        help="The order in which distribution lines are displayed and matched. For refunds to work properly, invoice distribution lines should be arranged in the same order as the credit note distribution lines they correspond to.")
    use_in_tax_closing = fields.Boolean(
        string="Tax Closing Entry",
        compute='_compute_use_in_tax_closing', store=True, readonly=False, precompute=True,
    )

    tag_ids_domain = fields.Binary(string="tag domain", help="Dynamic domain used for the tag that can be set on tax", compute="_compute_tag_ids_domain")

    @api.model_create_multi
    def create(self, vals):
        tax_ids = {tax_id for line in vals if (tax_id := line.get('tax_id'))}
        taxes = self.env['account.tax'].browse(tax_ids)
        for tax in taxes.filtered('is_used'):
            raise ValidationError(_("The tax named %s has already been used, you cannot add nor delete its tax repartition lines.", tax.name))
        return super().create(vals)

    def unlink(self):
        for repartition_line in self:
            if repartition_line.tax_id.is_used:
                raise ValidationError(_("The tax named %s has already been used, you cannot add nor delete its tax repartition lines.", repartition_line.tax_id.name))
        return super().unlink()

    @api.depends('company_id.multi_vat_foreign_country_ids', 'company_id.account_fiscal_country_id')
    def _compute_tag_ids_domain(self):
        for rep_line in self:
            allowed_country_ids = (False, rep_line.company_id.account_fiscal_country_id.id, *rep_line.company_id.multi_vat_foreign_country_ids.ids,)
            rep_line.tag_ids_domain = [('applicability', '=', 'taxes'), ('country_id', 'in', allowed_country_ids)]

    @api.depends('account_id', 'repartition_type')
    def _compute_use_in_tax_closing(self):
        for rep_line in self:
            rep_line.use_in_tax_closing = (
                rep_line.repartition_type == 'tax'
                and rep_line.account_id
                and rep_line.account_id.internal_group not in ('income', 'expense')
            )

    @api.depends('factor_percent')
    def _compute_factor(self):
        for record in self:
            record.factor = record.factor_percent / 100.0

    @api.onchange('repartition_type')
    def _onchange_repartition_type(self):
        if self.repartition_type == 'base':
            self.account_id = None

    def _get_aml_target_tax_account(self, force_caba_exigibility=False):
        """ Get the default tax account to set on a business line.

        :return: An account.account record or an empty recordset.
        """
        self.ensure_one()
        if not force_caba_exigibility and self.tax_id.tax_exigibility == 'on_payment' and not self._context.get('caba_no_transition_account'):
            return self.tax_id.cash_basis_transition_account_id
        else:
            return self.account_id
