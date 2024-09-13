from collections import deque, defaultdict
from contextlib import contextmanager
from datetime import datetime
from dateutil.relativedelta import relativedelta
import logging

from odoo.tools.sql import SQL
from odoo.fields import Many2one

_logger = logging.getLogger(__name__)

# Min/Max value for a date/datetime field
MIN_DATETIME = datetime((datetime.now() - relativedelta(years=4)).year, 1, 1)
MAX_DATETIME = datetime.now()
MIN_ROWS_PER_DAY = 1000


def vary_date_field(env, model, factors, min_date=MIN_DATETIME, max_date=MAX_DATETIME):
    """
    Spreads uniformly dates in the date range specified by [min_date, max_date]
    """
    total_table_size = model.search_count([]) * factors[model]
    if total_table_size <= MIN_ROWS_PER_DAY:
        return SQL('now()::timestamp')
    total_days = (max_date - min_date).days
    rows_per_day = max(MIN_ROWS_PER_DAY, total_table_size // total_days + 1)
    if total_table_size <= MIN_ROWS_PER_DAY * total_days:
        min_date = min_date + relativedelta(days=(total_days - total_table_size // MIN_ROWS_PER_DAY))
    return SQL("%s + (row_number() OVER() / %s) * interval '1 day'", min_date, rows_per_day)


def vary_char_field(env, model, field, postfix=None):
    """
    Append the `postfix` string to a char|text field.
    If no postfix is provided, returns no variation
    """
    if postfix is None:
        return field.name
    if not isinstance(postfix, SQL):
        postfix = SQL(f'{postfix}::text')
    # if the field is translatable, it's a JSONB column, we vary all values for each key
    if field.translate:
        return SQL("""
            CASE
                WHEN %(field)s IS NOT NULL
                THEN (
                    SELECT jsonb_object_agg(key, value || %(postfix)s)
                    FROM jsonb_each(%(field)s)
                )
                ELSE NULL
            END
        """, field=SQL.identifier(field.name), postfix=postfix)
    else:
        return SQL("""
            CASE
                WHEN %(field)s IS NULL OR %(field)s IN ('/', '')
                THEN %(field)s
                ELSE %(field)s || %(postfix)s
            END
        """, field=SQL.identifier(field.name), postfix=postfix)


@contextmanager
def ignore_indexes(env, tablename):
    """
    Temporarily drop indexes on table to speed up insertion.
    PKey and Unique indexes are kept for constraints
    """
    indexes = env.execute_query_dict(SQL("""
        SELECT indexname AS name, indexdef AS definition
          FROM pg_indexes
         WHERE tablename = %s
           AND indexname NOT LIKE %s
           AND indexdef NOT LIKE %s
    """, tablename, '%pkey', '%UNIQUE%'))
    if indexes:
        _logger.info('Dropping indexes on table %s...', tablename)
        env.cr.execute(SQL(';').join(
            SQL('DROP INDEX %s CASCADE', SQL.identifier(index['name']))
            for index in indexes
        ))
        yield
        _logger.info('Adding indexes back on table %s...', tablename)
        env.cr.execute(';'.join(index['definition'] for index in indexes))
    else:
        yield


@contextmanager
def ignore_fkey_constraints(env):
    """
    Disable Fkey constraints checks by setting the session to replica.
    """
    env.cr.execute('SET session_replication_role TO replica')
    yield
    env.cr.execute('RESET session_replication_role')


def field_need_variation(env, model, field):
    """
    Return True/False depending on if the field needs to be varied.
    Might be necessary in the case of:
    - unique constraints
    - varying dates for better distribution
    - field will be part of _rec_name_search, therefor variety is needed for effective searches
    - field has a trigram index on it
    """
    def is_unique(_env, _model, _field):
        """
        An unique constraint is enforced by Postgres as an unique index,
        whether it's defined as a constraint on the table, or as an manual unique index.
        Both type of constraint are present in the index catalog
        """
        query = SQL("""
        SELECT EXISTS(SELECT 1
              FROM pg_index idx
                   JOIN pg_class t ON t.oid = idx.indrelid
                   JOIN pg_class i ON i.oid = idx.indexrelid
                   JOIN pg_attribute a ON a.attnum = ANY (idx.indkey) AND a.attrelid = t.oid
              WHERE t.relname = %s  -- tablename
                AND a.attname = %s  -- column
                AND idx.indisunique = TRUE) AS is_unique;
        """, _model._table, _field.name)
        return _env.execute_query(query)[0][0]

    # many2one fields are not considered, as a name_search would resolve it to the _rec_names_search of the related model
    if model._rec_names_search and field.name in model._rec_names_search and field.type != 'many2one':
        return True
    if field.type in ('date', 'datetime'):
        return True
    if field.index == 'trigram':
        return True
    return is_unique(env, model, field)


def variate_field(env, model, field, table_alias, series_alias, factors):
    """
    Returns a variation of the source field,
    to avoid unique constraint, or better distribute data.

    :return: a str representing the source column, or an SQL(expression/subquery)
    """
    match field.type:
        case 'char' | 'text':
            return vary_char_field(env, model, field, postfix=series_alias)
        case 'date' | 'datetime':
            return vary_date_field(env, model, factors)
        case 'html':
            # For the sake of simplicity we don't vary html fields
            return field.name
        case _:
            _logger.warning("The field %s of type %s was marked to be varied, "
                            "but no variation branch was found! Defaulting to a raw copy.", field, field.type)
            # fallback on a raw copy
            return field.name


def fetch_last_id(env, model):
    query = SQL('SELECT id FROM %s ORDER BY id DESC LIMIT 1', SQL.identifier(model._table))
    return env.execute_query(query)[0][0]


def duplicate_field(env, model, field, duplicated, factors, table_alias='t', series_alias='s'):
    """
    Returns a tuple representing the destination and the source expression (str column or SQL expression)
    """
    def copy_noop():
        return None, None

    def copy_raw(_field):
        return _field.name, _field.name

    def copy(_field):
        if field_need_variation(env, model, _field):
            return _field.name, variate_field(env, model, _field, table_alias, series_alias, factors)
        else:
            return copy_raw(_field)

    def copy_id():
        last_id = fetch_last_id(env, model)
        duplicated[model] = last_id  # this adds the model in the duplicated dict
        return field.name, SQL(f'id + {last_id} * {series_alias}')

    def copy_many2one(_field):
        # if the comodel was priorly duplicated, remap the many2one to the new copies
        if (comodel := env[_field.comodel_name]) in duplicated:
            comodel_max_id = duplicated[comodel]
            # we use MOD() instead of %, because % cannot be correctly escaped, it's a limitation of the SQL wrapper
            return _field.name, SQL(f"{table_alias}.{_field.name} + {comodel_max_id} * (MOD({series_alias} - 1, {factors[comodel]}) + 1)")
        return copy(_field)

    if field.name == 'id':
        return copy_id()
    match field.type:
        case 'one2many':
            # there is nothing to copy, as it's value is implicitly read from the inverse Many2one
            return copy_noop()
        case 'many2many':
            # there is nothing to do, the copying of the m2m will be handled when copying the relation table
            return copy_noop()
        case 'many2one':
            return copy_many2one(field)
        case 'many2one_reference':
            # TODO: in the case of a reference field, there is no comodel,
            #  but it's specified as the value of the field specified by model_field.
            #  Not really sure how to handle this, as it involves reading the content pointed by model_field
            #  to check on-the-fly if it's duplicated or not python-side, so for now we raw-copy it.
            #  If we need to read on-the-fly, the duplicated structure needs to be in DB (via a new Model?)
            return copy(field)
        case 'binary':
            # copy only binary field that are inlined in the table
            return copy(field) if not field.attachment else copy_noop()
        case _:
            return copy(field)


def duplicate_model(env, model, duplicated, factors, char_separator_code):

    def update_sequence(_model):
        env.execute_query(SQL(f"SELECT SETVAL('{_model._table}_id_seq', {fetch_last_id(env, _model)}, TRUE)"))

    assert model not in duplicated, f"We do not duplicate a model ({model}) that has already been duplicated."
    _logger.info('Duplicating model %s %s times...', model._name, factors[model])
    dest_fields = []
    src_fields = []
    update_fields = []
    table_alias = 't'
    series_alias = 's'
    # process all stored fields (that has a respective column), if the model has an 'id', it's processed first
    has_column = lambda f: f.store and f.column_type
    for field in (f for f in sorted(model._fields.values(), key=lambda x: x.name != 'id') if has_column(f)):
        if field_need_variation(env, model, field) and field.type in ('char', 'text'):
            update_fields += [field]
        dest, src = duplicate_field(env, model, field, duplicated, factors, table_alias, series_alias)
        dest_fields += [dest if isinstance(dest, SQL) else SQL.identifier(dest)] if dest else []
        src_fields += [src if isinstance(src, SQL) else SQL.identifier(src)] if src else []
    # Update char/text fields for existing rows, to allow re-entrance
    if update_fields:
        query = SQL('UPDATE %(table)s SET (%(src_columns)s) = ROW(%(dest_columns)s)',
                    table=SQL.identifier(model._table),
                    src_columns=SQL(", ").join(SQL.identifier(field.name) for field in update_fields),
                    dest_columns=SQL(", ").join(
                        vary_char_field(env, model, field, postfix=SQL(f"CHR({char_separator_code})"))
                        for field in update_fields))
        env.cr.execute(query)
    query = SQL(f"""
        INSERT INTO %(table)s (%(dest_columns)s)
        SELECT %(src_columns)s FROM %(table)s {table_alias},
        GENERATE_SERIES(1, {factors[model]}) {series_alias}
    """, table=SQL.identifier(model._table),
         dest_columns=SQL(', ').join(dest_fields),
         src_columns=SQL(', ').join(src_fields))
    env.cr.execute(query)
    # normally copying the 'id' will set the model entry in the duplicated dict,
    # but for the case of a table with no 'id' (ex: Many2many), we add manually,
    # by reading the key and having the defaultdict do the insertion, with a default value of 0
    if duplicated[model]:
        # in case we duplicated a model with an 'id', we update the sequence
        update_sequence(model)


def infer_many2many_model(env, field):
    """
    Returns the relation model used for the m2m:
    - If it's a custom model, return the model
    - If it's an implicite table generated by the ORM,
      return a wrapped model that behaves like a fake duck-typed model for the duplication algorithm
    """

    class Many2oneFieldWrapper(Many2one):
        def __init__(self, model, field_name, comodel_name):
            super().__init__(comodel_name)
            self._setup_attrs(model, field_name)  # setup most of the default attrs

    class Many2manyModelWrapper:
        def __init__(self, field):
            self._name = field.relation  # a m2m doesn't have a _name, so we use the tablename
            self._table = field.relation
            self._inherits = {}
            self.env = env
            self._rec_names_search = []
            # if the field is inherited, the column attributes are defined on the base_field
            column1 = field.column1 if field.column1 else field.base_field.column1
            column2 = field.column2 if field.column2 else field.base_field.column2
            # column1 refers to the model, while column2 refers to the comodel
            self._fields = {
                field.column1: Many2oneFieldWrapper(self, column1, field.model_name),
                field.column2: Many2oneFieldWrapper(self, column2, field.comodel_name),
            }

        def __repr__(self):
            return self._name

        def __eq__(self, other):
            return self._name == other._name

        def __hash__(self):
            return hash(self._name)

    # check if the relation is an existing model
    if model := next((model for model in env.registry.models.values() if model._table == field.relation), None):
        return env[model._name]  # `model` is a MetaModel, re-fetch from env to get the actual ORM model
    # the relation is a relational table, return a wrapped version
    return Many2manyModelWrapper(field)


def duplicate_models(env, models, factors, char_separator_code):
    """
    Create factors new records using existing records as templates.

    If a dependency is found for a specific model, but it isn't specified by the user,
    it will inherit the factor of the dependant model.

    :param: list(BaseModel) models: models to duplicate.
    :param: dict(int) factors: duplication factor by model.
    """

    def has_records(_model):
        query = SQL('SELECT EXISTS (SELECT 1 FROM %s)', SQL.identifier(_model._table))
        return _model.env.execute_query(query)[0][0]

    to_process = deque(models)
    duplicated = defaultdict(int)  # {model: int(old_max_id)}
    while to_process:
        model = to_process.popleft()
        if not has_records(model):  # if there are no records, there is nothing to duplicate
            continue
        # if the model has _inherits, the delegated models need to have been duplicated before the current one
        missing_dependencies = [m for model_name in model._inherits if (m := env[model_name]) not in duplicated]
        if missing_dependencies:
            pending_dependencies = [dep for dep in missing_dependencies if dep not in to_process]
            if pending_dependencies:
                to_process.extendleft([model] + pending_dependencies)
                factors.update({dep: factors[model] for dep in pending_dependencies})
                continue
        # models on the other end of X2many relation should also be duplicated (ex: to avoid SO with no SOL)
        for field in (f for f in model._fields.values() if f.store and f.copy):
            match field.type:
                case 'one2many':
                    comodel = env[field.comodel_name]
                    if comodel != model and comodel not in duplicated and comodel not in to_process:
                        to_process.append(comodel)
                        factors[comodel] = factors[model]
                case 'many2many':
                    m2m_model = infer_many2many_model(env, field)
                    if m2m_model not in duplicated and m2m_model not in to_process:
                        to_process.append(m2m_model)
                        factors[m2m_model] = factors[model]
                case _:
                    continue
        with ignore_fkey_constraints(env), ignore_indexes(env, model._table):
            duplicate_model(env, model, duplicated, factors, char_separator_code)
