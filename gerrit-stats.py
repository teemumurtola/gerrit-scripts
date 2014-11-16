#!/usr/bin/python
#
# Copyright (c) 2014, Teemu Murtola

"""Computes statistics from Gerrit changes"""

import subprocess

import gerrit.query
import gerrit.records
from statistics import Statistics, StatisticsAuthorNameColumn, \
        StatisticsCountColumn, StatisticsDistinctCountColumn

class AuthorChangeActivity(object):

    title = "Number of changes during past N days"

    def do_stats(self, fp, records):
        stats = Statistics([StatisticsAuthorNameColumn('Name', lambda x : x.author)])
        stats.process_records(records.change_activity, [
            StatisticsCountColumn('Created', lambda x : x.created_on),
            StatisticsCountColumn('Merged', lambda x : x.merged_on),
            StatisticsCountColumn('Abandoned', lambda x : x.abandoned_on)
            ])
        stats.process_records(records.comments, [
            StatisticsDistinctCountColumn('Commented', lambda x : x.change if x.timestamp else None)
            ])
        stats.process_records(records.votes, [
            StatisticsDistinctCountColumn('Voted', lambda x : x.change if x.timestamp else None)
            ])
        stats.print_stats(fp, sort_by='Voted')


class AuthorOpenChanges(object):

    title = "Number of open changes"

    def do_stats(self, fp, records):
        stats = Statistics([StatisticsAuthorNameColumn('Name', lambda x : x.author)])
        stats.process_records(records.open_changes, [
            StatisticsCountColumn('Open', lambda x : True),
            StatisticsCountColumn('RFC/WIP', lambda x : x.is_rfc_wip),
            StatisticsCountColumn('-Verified',
                lambda x : not x.is_rfc_wip and not x.is_verified),
            StatisticsCountColumn('-Review',
                lambda x : not x.is_rfc_wip and x.is_verified and x.is_downvoted),
            StatisticsCountColumn('Approved',
                lambda x : not x.is_rfc_wip and x.is_verified and x.is_approved),
            StatisticsCountColumn('+Review',
                lambda x : not x.is_rfc_wip and x.is_verified and not x.is_approved and x.is_upvoted),
            StatisticsCountColumn('Comments',
                lambda x : not x.is_rfc_wip and x.is_verified and not x.is_upvoted and not x.is_downvoted and x.has_comments),
            StatisticsCountColumn('Nothing',
                lambda x : not x.is_rfc_wip and x.is_verified and not x.has_comments)
            ])
        stats.print_stats(fp, sort_by='Open')


class AuthorOpenChangeActivity(object):

    title = "Activity on open changes"

    def do_stats(self, fp, records):
        stats = Statistics([StatisticsAuthorNameColumn('Name', lambda x : x.author)])
        stats.process_records(records.open_comments, [
            StatisticsDistinctCountColumn('Commented', lambda x : x.change)
            ])
        stats.process_records(records.open_votes, [
            StatisticsDistinctCountColumn('Voted', lambda x : x.change)
            ])
        stats.print_stats(fp, sort_by='Commented')


class AuthorActivity(object):

    title = "Activity (number of actions) during past N days"

    def do_stats(self, fp, records):
        stats = Statistics([StatisticsAuthorNameColumn('Name', lambda x : x.author)])
        stats.process_records(records.comments, [
            StatisticsCountColumn('Comments', lambda x : x.timestamp)
            ])
        stats.process_records(records.technical_comments, [
            StatisticsCountColumn('Technical', lambda x : x.timestamp)
            ])
        stats.process_records(records.votes, [
            StatisticsCountColumn('Votes', lambda x : x.timestamp)
            ])
        stats.print_stats(fp, sort_by='Comments')

def main():
    """Main function for the script"""

    import argparse
    import os.path
    import sys

    parser = argparse.ArgumentParser(description='Compute Gerrit statistics')
    parser.add_argument('--cache',
                        help='Cache file to use')
    parser.add_argument('--update-cache', action='store_true',
                        help='Update the contents of the cache file')
    parser.add_argument('--days', type=int, default=30,
                        help='Number of past days to count activity over')
    parser.add_argument('--all', dest='all_stats', action='store_true',
                        help='Print all types of statistics')
    parser.add_argument('--open-by-author', dest='stats', action='append_const',
                        const=AuthorOpenChanges,
                        help='Print statistics on number of open changes by author')
    parser.add_argument('--open-activity', dest='stats', action='append_const',
                        const=AuthorOpenChangeActivity,
                        help='Print statistics on activity on open changes by author')
    parser.add_argument('--change-activity', dest='stats', action='append_const',
                        const=AuthorChangeActivity,
                        help='Print statistics on activity on changes by author')
    parser.add_argument('--activity', dest='stats', action='append_const',
                        const=AuthorActivity,
                        help='Print statistics on recent activity by author')
    args = parser.parse_args()

    stats = args.stats
    if not stats or args.all_stats:
        stats = [AuthorOpenChanges, AuthorOpenChangeActivity,
                AuthorChangeActivity, AuthorActivity]

    if not args.cache or args.update_cache or not os.path.exists(args.cache):
        query = ['ssh', '-p', '29418', 'gerrit.gromacs.org', 'gerrit', 'query',
                '--format=JSON', '--all-approvals', '--comments', '--',
                '-age:{0}d'.format(args.days), 'OR', 'status:open']
        query_results = subprocess.check_output(query)
        if args.update_cache:
            with open(args.cache, 'w') as fp:
                fp.write(query_results)
    elif args.cache:
        with open(args.cache, 'r') as fp:
            query_results = fp.read()

    data = gerrit.query.GerritQueryResults(query_results)
    records = gerrit.records.GerritRecords(data, 30)

    first = True
    for stat_type in stats:
        if not first:
            sys.stdout.write('\n\n')
        stat = stat_type()
        sys.stdout.write(stat.title + '\n\n')
        stat.do_stats(sys.stdout, records)
        first = False

if __name__ == '__main__':
    main()
