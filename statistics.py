# Copyright (c) 2014, Teemu Murtola

import copy

class StatisticsColumn(object):
    def __init__(self, name):
        self.name = name

    @property
    def default_value(self):
        return 0

    def to_sortable(self, value):
        return value

    def to_string(self, value):
        return unicode(value)

    def accumulate(self, base, value):
        return base + value


class StatisticsAuthorNameColumn(StatisticsColumn):
    def __init__(self, name, get_author):
        StatisticsColumn.__init__(self, name)
        self._get_author = get_author

    def get_value(self, record):
        return self._get_author(record).fullname


class StatisticsCountColumn(StatisticsColumn):
    def __init__(self, name, predicate):
        StatisticsColumn.__init__(self, name)
        self._predicate = predicate

    def get_value(self, record):
        if self._predicate(record):
            return 1
        return 0


class StatisticsDistinctCountColumn(StatisticsColumn):
    def __init__(self, name, predicate):
        StatisticsColumn.__init__(self, name)
        self._predicate = predicate

    @property
    def default_value(self):
        return set()

    def get_value(self, record):
        return self._predicate(record)

    def to_sortable(self, value):
        return len(value)

    def to_string(self, value):
        return unicode(len(value))

    def accumulate(self, base, value):
        if value:
            base.add(value)
        return base


class Statistics(object):
    def __init__(self, group_columns):
        self._group_columns = group_columns
        self._columns = list()
        self._init_values = list()
        self._groups = dict()

    def process_records(self, records, columns):
        existing_columns = len(self._columns)
        self._columns.extend(columns)
        new_init_values = [column.default_value for column in columns]
        self._init_values.extend(new_init_values)
        for group in self._groups.itervalues():
            group.extend(copy.deepcopy(new_init_values))
        for record in records:
            group = self._get_group(record)
            for index, column in enumerate(columns, existing_columns):
                value = column.get_value(record)
                group[index] = column.accumulate(group[index], value)

    def _get_group(self, record):
        key = tuple(column.get_value(record) for column in self._group_columns)
        group = self._groups.get(key)
        if not group:
            group = copy.deepcopy(self._init_values)
            self._groups[key] = group
        return group

    def _find_column_index(self, column_name):
        for index, column in enumerate(self._group_columns):
            if column.name == column_name:
                return index
        for index, column in enumerate(self._columns, len(self._group_columns)):
            if column.name == column_name:
                return index
        raise ValueError('Unknown column name: ' + column_name)

    def print_stats(self, fp, sort_by=None):
        all_columns = self._group_columns + self._columns
        titles = [column.name for column in all_columns]
        lines = [list(key) + value for key, value in self._groups.iteritems()
                if any([value[i] != column.default_value
                    for i, column in enumerate(self._columns)])]
        if sort_by:
            sort_by_index = self._find_column_index(sort_by)
            column = all_columns[sort_by_index]
            lines.sort(key=lambda x: column.to_sortable(x[sort_by_index]), reverse=True)
        widths = list()
        for index, column in enumerate(all_columns):
            max_value_len = max([len(column.to_string(x[index])) for x in lines])
            widths.append(max(len(titles[index]), max_value_len))
        for elem, width in zip(titles, widths):
            fp.write(u'{0:{width}} '.format(elem, width=width));
        fp.write('\n')
        for width in widths:
            fp.write(u'{0:=^{width}} '.format('', width=width));
        fp.write('\n')
        for line in lines:
            for elem, column, width in zip(line, all_columns, widths):
                fp.write(u'{0:{width}} '.format(column.to_string(elem), width=width));
            fp.write('\n')


