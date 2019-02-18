from unittest import skip

from eventsourcing.tests.sequenced_item_tests.test_django_record_manager import DjangoTestCase
from eventsourcing.application.django import DjangoApplication
from eventsourcing.tests.test_actors import TestActors


class TestActorsWithDjango(DjangoTestCase, TestActors):
    infrastructure_class = DjangoApplication

    @skip("Having trouble running Thespian's 'multiproc tcp base' twice")
    def test_multiproc_tcp_base(self):
        super(TestActorsWithDjango, self).test_multiproc_tcp_base()
