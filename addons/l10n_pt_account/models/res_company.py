# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError
from odoo.tools.misc import format_date, groupby
from odoo.addons.l10n_pt.utils.hashing import L10nPtHashingUtils


class ResCompany(models.Model):
    _inherit = "res.company"

    def _check_accounting_hash_integrity(self):
        """Checks that all posted moves have still the same data as when they were posted
        and raises an error with the result.
        """
        if self.account_fiscal_country_id.code != 'PT':
            return super()._check_accounting_hash_integrity()

        # if not self.env.user.has_group('account.group_account_user'):
        #     raise UserError(_('Please contact your accountant to print the Hash integrity result.'))

        journals = self.env['account.journal'].search([('company_id', '=', self.id)])
        results = []

        self.env['account.move'].l10n_pt_account_compute_missing_hashes(self.env.company.id)

        for journal in journals:
            if not journal.restrict_mode_hash_table:
                results.append({
                    'name': f"{journal.name} [{journal.code}]",
                    'status': 'not_checked',
                    'msg': _('This journal is not in strict mode.'),
                })
                continue

            # We need the `sudo()` to ensure that all the moves are searched, no matter the user's access rights.
            # This is required in order to generate consistent hashes.
            # It is not an issue, since the data is only used to compute a hash and not to return the actual values.
            all_moves = self.env['account.move'].sudo().search([
                ('journal_id', '=', journal.id),
                ('inalterable_hash', '!=', False),
            ])
            if not all_moves:
                results.append({
                    'name': f"{journal.name} [{journal.code}]",
                    'status': 'no_data',
                    'msg': _('There is no journal entry flagged for data inalterability yet.'),
                })
                continue

            grouped = groupby(all_moves, key=lambda m: m.sequence_prefix)

            if self.env['ir.config_parameter'].sudo().get_param('l10n_pt.iap_endpoint') == 'demo':
                public_key_string = self.env['ir.config_parameter'].sudo().get_param('l10n_pt.public_key')
            else:
                public_keys = L10nPtHashingUtils._l10n_pt_get_public_keys(self.env)
                public_key_string = public_keys[max(public_keys, key=int)]
            if not public_key_string:
                raise UserError(_("The public key for the local hash verification in Portugal is not set."))

            hash_corrupted = False
            for prefix, moves in grouped:
                moves = sorted(moves, key=lambda m: m.sequence_number)
                previous_hash = ''
                for move in moves:
                    if not move._l10n_pt_account_verify_integrity(previous_hash, public_key_string):
                        results.append({
                            'name': f"{journal.name} [{prefix}]",
                            'status': 'corrupted',
                            'msg': _("Corrupted data on journal entry with id %s.", move.id),
                        })
                        hash_corrupted = True
                        break
                    previous_hash = move.inalterable_hash

                if not hash_corrupted:
                    results.append({
                        'name': f"{journal.name} [{prefix}]",
                        'status': 'verified',
                        'msg': _("Entries are correctly hashed"),
                        'from_name': moves[0].name,
                        'from_hash': moves[0].inalterable_hash,
                        'from_date': fields.Date.to_string(moves[0].date),
                        'to_name': moves[-1].name,
                        'to_hash': moves[-1].inalterable_hash,
                        'to_date': fields.Date.to_string(moves[-1].date),
                    })

        return {
            'results': results,
            'printing_date': format_date(self.env, fields.Date.to_string(fields.Date.context_today(self)))
        }
