"""EVENT_CHANNEL unit tests."""
from src.routes.notification import EVENT_CHANNEL


REQUIRED_EVENTS = {
    "OrderPending", "OrderApproved", "OrderRejected",
    "AutoExecutedUrgent", "AutoRejectedBatch", "SpikeUrgent",
    "StockDepartPending", "StockArrivalPending", "NewBookRequest",
    "ReturnPending", "LambdaAlarm", "DeploymentRollback",
    "NewBookSubmittedToHq", "NewBookAcceptedToPublisher",
    "NewBookRejectedToPublisher", "NewBookDisplayRequest",
}


def test_event_channel_has_required_events():
    assert REQUIRED_EVENTS.issubset(set(EVENT_CHANNEL.keys()))


def test_new_book_notice_events_do_not_publish_to_redis():
    assert EVENT_CHANNEL["NewBookSubmittedToHq"] is None
    assert EVENT_CHANNEL["NewBookAcceptedToPublisher"] is None
    assert EVENT_CHANNEL["NewBookRejectedToPublisher"] is None
    assert EVENT_CHANNEL["NewBookDisplayRequest"] is None


def test_core_event_channels():
    assert EVENT_CHANNEL["OrderPending"] == "order.pending"
    assert EVENT_CHANNEL["OrderApproved"] == "order.approved"
    assert EVENT_CHANNEL["OrderRejected"] == "order.rejected"
    assert EVENT_CHANNEL["AutoExecutedUrgent"] == "order.dispatched"
    assert EVENT_CHANNEL["SpikeUrgent"] == "spike.detected"
    assert EVENT_CHANNEL["NewBookRequest"] == "newbook.request"


def test_no_invalid_channel_names():
    valid = {
        "order.pending", "order.approved", "order.dispatched", "order.executed",
        "order.rejected", "spike.detected", "newbook.request", "stock.changed", None,
    }
    for ev, ch in EVENT_CHANNEL.items():
        assert ch in valid, f"{ev}: {ch} is not a valid notification channel"
