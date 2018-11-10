from eventsourcing.exceptions import RecordConflictError
from eventsourcing.infrastructure.base import ACIDRecordManager


class PopoNotification(object):
    def __init__(self, notification_id, originator_id, originator_version, event_type, state):
        self.notification_id = notification_id
        self.originator_id = originator_id
        self.originator_version = originator_version
        self.event_type = event_type
        self.state = state


class PopoRecordManager(ACIDRecordManager):

    def __init__(self, *args, **kwargs):
        super(PopoRecordManager, self).__init__(*args, **kwargs)
        self._all_sequence_records = {}
        self._all_tracking_records = {}
        self._all_notification_records = {}

    def all_sequence_ids(self):
        try:
            return self._all_sequence_records[self.application_name].keys()
        except KeyError:
            return []

    def delete_record(self, record):
        sequence_records = self._get_sequence_records(record.sequence_id)
        try:
            position = getattr(record, self.field_names.position)
            del(sequence_records[position])
        except KeyError:
            pass

    def get_max_record_id(self):
        notification_records = self._get_notification_records()
        try:
            return max(notification_records.keys())
        except ValueError:
            pass

    def _get_notification_records(self):
        try:
            notification_records = self._all_notification_records[self.application_name]
        except KeyError:
            notification_records = {}
            self._all_notification_records[self.application_name] = notification_records
        return notification_records

    def get_notifications(self, start=None, stop=None, *args, **kwargs):
        notification_records = self._get_notification_records()
        for i in range(start + 1, stop + 1):
            try:
                notification_record = notification_records[i]
                notification = PopoNotification(
                    notification_id=notification_record['notification_id'],
                    originator_id=notification_record['sequenced_item'].originator_id,
                    originator_version=notification_record['sequenced_item'].originator_version,
                    event_type=notification_record['sequenced_item'].event_type,
                    state=notification_record['sequenced_item'].state,

                )
                yield notification
            except KeyError:
                pass

    def get_max_tracking_record_id(self, upstream_application_name):
        tracking_records = self._get_tracking_records(upstream_application_name)
        try:
            return max(tracking_records.keys())
        except ValueError:
            pass

    def _get_tracking_records(self, upstream_application_name):
        try:
            tracking_records = self._all_tracking_records[upstream_application_name]
        except KeyError:
            tracking_records = {}
            self._all_tracking_records[upstream_application_name] = tracking_records
        return tracking_records

    def get_record(self, sequence_id, position):
        try:
            return self._get_sequence_records(sequence_id)[position]
        except KeyError:
            raise IndexError(self.application_name, sequence_id, position)

    def get_records(self, sequence_id, gt=None, gte=None, lt=None, lte=None, limit=None,
                    query_ascending=True, results_ascending=True):

        start = None
        if gt is not None:
            start = gt + 1
        if gte is not None:
            if start is None:
                start = gte
            else:
                start = max(start, gte)

        end = None
        if lt is not None:
            end = lt
        if lte is not None:
            if end is None:
                end = lte + 1
            else:
                end = min(end, lte + 1)

        all_sequence_records = self._get_sequence_records(sequence_id)
        if not len(all_sequence_records):
            return []

        if end is None:
            end = max(all_sequence_records.keys()) + 1
        if start is None:
            start = min(all_sequence_records.keys())

        selected_records = []
        for position in range(start, end):
            try:
                record = all_sequence_records[position]
            except KeyError:
                pass
            else:
                selected_records.append(record)

        if not query_ascending:
            selected_records = reversed(selected_records)

        if limit is not None:
            selected_records = list(selected_records)[:limit]

        if query_ascending != results_ascending:
            selected_records = reversed(selected_records)

        return selected_records

    def _get_sequence_records(self, sequence_id):
        try:
            return self._all_sequence_records[self.application_name][sequence_id]
        except KeyError:
            return {}

    def has_tracking_record(self, upstream_application_name, pipeline_id, notification_id):
        raise NotImplementedError()

    def record(self, sequenced_item_or_items):
        if isinstance(sequenced_item_or_items, list):
            for sequenced_item in sequenced_item_or_items:
                self._record_sequenced_item(sequenced_item)
        else:
            self._record_sequenced_item(sequenced_item_or_items)

    def _record_sequenced_item(self, sequenced_item):
        position = getattr(sequenced_item, self.field_names.position)
        if not isinstance(position, int):
            raise NotImplementedError("Popo record manager only supports sequencing with integers, "
                                      "but position was a {}".format(type(position)))

        sequence_id = getattr(sequenced_item, self.field_names.sequence_id)
        try:
            application_records = self._all_sequence_records[self.application_name]
        except KeyError:
            sequence_records = {}
            application_records = {sequence_id: sequence_records}
            self._all_sequence_records[self.application_name] = application_records
        else:
            try:
                sequence_records = application_records[sequence_id]
            except KeyError:
                sequence_records = {}
                application_records[sequence_id] = sequence_records


        if position in sequence_records:
            raise RecordConflictError(position, len(sequence_records))

        sequence_records[position] = sequenced_item

        # Write a notification record.
        notification_records = self._get_notification_records()
        next_notification_id = (self.get_max_record_id() or 0) + 1
        notification_records[next_notification_id] = {
            'notification_id': next_notification_id,
            'sequenced_item': sequenced_item,
        }

    def write_records(self, records, tracking_kwargs=None):
        self.record(records)

    def to_records(self, sequenced_items):
        return sequenced_items