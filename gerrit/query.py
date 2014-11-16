# Copyright (c) 2014, Teemu Murtola

"""Classes to parse, store, and interpret `gerrit query` results."""

import datetime
import json
import re

def _convert_time(timestamp):
    """Convert Gerrit timestamps to Python objects."""
    if not timestamp:
        return None
    return datetime.datetime.fromtimestamp(timestamp)


class Approval(object):

    """Data for a vote on a Gerrit patch set."""

    class Type(object):

        """Enumeration for approval types."""

        code_review = 'Code-Review'
        submit = 'SUBM'
        verified = 'Verified'

    def __init__(self, approval_json, resolve_author):
        self.approval_type = approval_json.get('type')
        self.value = approval_json.get('value')
        if self.value is not None:
            self.value = int(self.value)
        self.granted_on = _convert_time(approval_json.get('grantedOn'))
        self.by = resolve_author(approval_json.get('by'))


class Author(object):

    """Data for a Gerrit author."""

    def __init__(self, username, fullname):
        self.username = username
        self.fullname = fullname

    @property
    def technical_account(self):
        return self.username in ('gerrit@gerrit.gromacs.org', 'jenkins')


class Change(object):

    """Data for a single Gerrit change."""

    class Status(object):

        """Enumeration for change statuses."""

        abandoned = 'ABANDONED'
        draft = 'DRAFT'
        merged = 'MERGED'
        submitted = 'SUBMITTED'
        new = 'NEW'

    def __init__(self, change_json, resolve_author):
        self.project = change_json.get('project')
        self.branch = change_json.get('branch')
        self.change_id = change_json.get('id')
        self.number = change_json.get('number')
        self.owner = resolve_author(change_json.get('owner'))
        self.commit_message = change_json.get('commitMessage')
        self.created_on = _convert_time(change_json.get('createdOn'))
        self.last_updated = _convert_time(change_json.get('lastUpdated'))
        self.status = change_json.get('status')
        self.comments = list()
        comments_json = change_json.get('comments')
        if comments_json:
            for comment_json in comments_json:
                self.comments.append(ChangeComment(comment_json, resolve_author))
        self.patchsets = list()
        patchsets_json = change_json.get('patchSets')
        if patchsets_json:
            for patchset_json in patchsets_json:
                self.patchsets.append(PatchSet(patchset_json, resolve_author))
        self.review_comments = list([comment for comment in self.comments
                if comment.reviewer != self.owner
                and not comment.reviewer.technical_account
                and not comment.technical_comment])
        self.technical_comments = list([comment for comment in self.comments
                if comment.reviewer != self.owner
                and not comment.reviewer.technical_account
                and comment.technical_comment])

    @property
    def last_patchset(self):
        return self.patchsets[-1]

    @property
    def merged_on(self):
        if self.status != Change.Status.merged:
            return None
        submission = self.last_patchset.get_approvals(Approval.Type.submit)
        assert len(submission) == 1
        return submission[0].granted_on

    @property
    def abandoned_on(self):
        if self.status != Change.Status.abandoned:
            return None
        for comment in reversed(self.comments):
            if comment.message.startswith('Abandoned'):
                return comment.timestamp
        return None

    @property
    def is_draft(self):
        return self.status == Change.Status.draft

    @property
    def is_open(self):
        return self.status in (Change.Status.new, Change.Status.submitted)

    @property
    def is_verified(self):
        votes = self.last_patchset.get_approvals(Approval.Type.verified)
        return any([vote.value == 2 for vote in votes]) and \
                not any([vote.value < 0 for vote in votes])

    @property
    def is_approved(self):
        votes = self.last_patchset.get_approvals(Approval.Type.code_review)
        return any([vote.value == 2 for vote in votes]) \
                and not any([vote.value < 0 for vote in votes])

    @property
    def is_downvoted(self):
        votes = self.last_patchset.get_approvals(Approval.Type.code_review)
        return any([vote.value < 0 for vote in votes])

    @property
    def is_upvoted(self):
        votes = self.last_patchset.get_approvals(Approval.Type.code_review)
        return any([vote.value > 0 for vote in votes]) \
                and not any([vote.value < 0 for vote in votes])


class ChangeComment(object):

    """Data for a comment on a Gerrit change."""

    def __init__(self, comment_json, resolve_author):
        self.timestamp = _convert_time(comment_json.get('timestamp'))
        self.reviewer = resolve_author(comment_json.get('reviewer'))
        self.message = comment_json.get('message')

    @property
    def technical_comment(self):
        match_re = r'(Change has been successfully|Patch Set \d+: (Patch Set \d+ was rebased|Commit message was updated)$|Uploaded patch set)'
        return bool(re.match(match_re, self.message))


class PatchSet(object):

    """Data for a patch set in a Gerrit change."""

    def __init__(self, patchset_json, resolve_author):
        self.number = patchset_json['number']
        self.uploader = resolve_author(patchset_json.get('uploader'))
        self.created_on = _convert_time(patchset_json.get('createdOn'))
        self.author = resolve_author(patchset_json.get('author'))
        self.draft = patchset_json.get('isDraft')
        self.sizeInsertions = patchset_json.get('sizeInsertions')
        self.sizeDeletions = patchset_json.get('sizeDeletions')
        self._approvals = list()
        approvals_json = patchset_json.get('approvals')
        if approvals_json:
            for approval_json in approvals_json:
                self._approvals.append(Approval(approval_json, resolve_author))

    def get_approvals(self, approval_type):
        return [approval for approval in self._approvals
                if approval.approval_type == approval_type]


class GerritQueryResults(object):

    """Parses and stores data retrieved from `gerrit query`."""

    def __init__(self, query_results):
        self._authors = dict()
        self._changes = list()
        for line in query_results.splitlines():
            entry = json.loads(line)
            entry_type = entry.get('type')
            if entry_type and entry_type == 'stats':
                # TODO: Parse the stats
                continue
            self._add_change(entry)
        self._public_changes = filter(lambda x: not x.is_draft, self._changes)
        self._open_changes = filter(lambda x: x.is_open, self._public_changes)

    @property
    def public_changes(self):
        """Return all non-draft changes."""
        return self._public_changes

    @property
    def open_changes(self):
        """Return all open non-draft changes."""
        return self._open_changes

    def _add_change(self, change_json):
        """Add a change from a decoded JSON entry."""
        self._changes.append(Change(change_json, self._resolve_author))

    def _resolve_author(self, author_json):
        """Add/resolve an author from a decoded JSON entry."""
        if not author_json:
            return None
        username = author_json.get('username')
        if not username:
            # If username is not specified, hopefully the e-mail is unique.
            # This gets triggered for some duplicate users, as well as for the
            # internal Gerrit user.
            # TODO: Consider merging duplicate users, if they can be recognized.
            username = author_json.get('email')
            assert username
        author = self._authors.get(username)
        if not author:
            author = Author(username, author_json.get('name'))
            self._authors[username] = author
        return author
