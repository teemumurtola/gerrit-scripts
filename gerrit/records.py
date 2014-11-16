# Copyright (c) 2014, Teemu Murtola

"""Classes to represent Gerrit events as a flat list of records."""

import datetime

import gerrit.query

class ChangeRecord(object):

    """Record of Gerrit change creation/submission."""

    def __init__(self, change, created_on, merged_on, abandoned_on):
        self._change = change
        self.created_on = created_on
        self.merged_on = merged_on
        self.abandoned_on = abandoned_on

    @property
    def author(self):
        return self._change.owner

    @property
    def is_open(self):
        return self._change.is_open

    @property
    def is_verified(self):
        return self._change.is_verified

    @property
    def is_approved(self):
        return self._change.is_approved

    @property
    def is_upvoted(self):
        return self._change.is_upvoted

    @property
    def is_downvoted(self):
        return self._change.is_downvoted

    @property
    def has_comments(self):
        return bool(self._change.review_comments)

    @property
    def is_rfc_wip(self):
        return self._change.commit_message.startswith(('RFC', '[RFC]', 'WIP', '[WIP]'))


class CommentRecord(object):

    """Record of comment on a Gerrit change."""

    def __init__(self, change, author, timestamp):
        self.change = change
        self.author = author
        self.timestamp = timestamp


class VoteRecord(object):

    """Record of a vote on a Gerrit change."""

    def __init__(self, change, author, timestamp):
        self.change = change
        self.author = author
        self.timestamp = timestamp


class GerritRecords(object):

    """Collection of records from Gerrit data.

    This class converts the hierarchical structure of
    gerrit.query.GerritQueryResults into flat lists of records from which
    various statistics can be calculated.
    """

    def __init__(self, data, activity_days):
        self._data = data
        self._cutoff_date = datetime.date.today() - datetime.timedelta(days=activity_days)
        self._change_activity = None
        self._comments = None
        self._technical_comments = None
        self._votes = None
        self._open_changes = None
        self._open_comments = None
        self._open_votes = None

    @property
    def change_activity(self):
        if self._change_activity is None:
            self._change_activity = self._get_change_records(self._data.public_changes)
        return self._change_activity

    @property
    def open_changes(self):
        if self._open_changes is None:
            self._open_changes = self._get_change_records(self._data.open_changes)
        return self._open_changes

    @property
    def comments(self):
        if self._comments is None:
            self._comments = self._get_comment_records(self._data.public_changes,
                    lambda x: x.review_comments)
        return self._comments

    @property
    def technical_comments(self):
        if self._technical_comments is None:
            self._technical_comments = self._get_comment_records(self._data.public_changes,
                    lambda x: x.technical_comments)
        return self._technical_comments

    @property
    def open_comments(self):
        if self._open_comments is None:
            self._open_comments = self._get_comment_records(self._data.open_changes,
                    lambda x: x.review_comments)
        return self._open_comments

    @property
    def votes(self):
        if self._votes is None:
            self._votes = self._get_vote_records(self._data.public_changes)
        return self._votes

    @property
    def open_votes(self):
        if self._open_votes is None:
            self._open_votes = self._get_vote_records(self._data.open_changes)
        return self._open_votes

    def _to_record_date(self, date):
        if date and date.date() < self._cutoff_date:
            return None
        return date

    def _get_change_records(self, changes):
        result = list()
        for change in changes:
            created_on = self._to_record_date(change.created_on)
            merged_on = self._to_record_date(change.merged_on)
            abandoned_on = self._to_record_date(change.abandoned_on)
            record = ChangeRecord(change, created_on, merged_on, abandoned_on)
            result.append(record)
        return result

    def _get_comment_records(self, changes, get_comments):
        result = list()
        for change in changes:
            for comment in get_comments(change):
                timestamp = self._to_record_date(comment.timestamp)
                record = CommentRecord(change, comment.reviewer, timestamp)
                result.append(record)
        return result

    def _get_vote_records(self, changes):
        result = list()
        for change in changes:
            for patchset in change.patchsets:
                for approval in patchset.get_approvals(gerrit.query.Approval.Type.code_review):
                    timestamp = self._to_record_date(approval.granted_on)
                    record = VoteRecord(change, approval.by, timestamp)
                    result.append(record)
        return result

