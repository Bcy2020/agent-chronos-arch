"""
Decomposer mental model test: 10 root nodes with full SubPRD context.

Each case provides everything needed to call decomposer.decompose():
  - node: Node object (node_id, name, purpose, inputs, outputs, global_vars, data_sources, boundary, subprd)
  - expected_children_range: (min, max) expected child count
  - tags: list of structural patterns to look for

Usage:
    from test_data.decomposer_cases import get_cases
    cases = get_cases()
    for case in cases:
        node = case["node"]
        # pass node to decomposer.decompose(node)
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "mvp", "mvp-0.4.4"))

from models import (
    Node, InputParam, OutputParam, Boundary, GlobalVar, DataSource,
    SubPRD, AcceptanceCriterion,
)


def _make_case(node_id, name, purpose, inputs, outputs, global_vars,
               data_sources, subprd_desc, subprd_constraints, subprd_acs,
               tags=None, expected_children_range=(3, 8)):
    node = Node(
        node_id=node_id, name=name, purpose=purpose, depth=0,
        inputs=[InputParam(**i) for i in inputs],
        outputs=[OutputParam(**o) for o in outputs],
        global_vars=[GlobalVar(**g) for g in global_vars],
        data_sources=[DataSource(
            name=d["name"], category=d.get("category", "database"),
            access=d.get("access", "read_write"), description=d.get("description", ""),
        ) for d in data_sources],
        boundary=Boundary(),
        subprd=SubPRD(
            description=subprd_desc,
            constraints=subprd_constraints,
            acceptance_criteria=[AcceptanceCriterion(**ac) for ac in subprd_acs],
        ),
    )
    return {"node": node, "expected_children_range": expected_children_range, "tags": tags or []}


# =======================================================================
# Case 1: E-commerce Order System (command-dispatch pattern)
# =======================================================================
CASE_01_ORDER = _make_case(
    node_id="root_order", name="OrderSystem",
    purpose="Process e-commerce orders via a single entry point. "
            "The function receives a command string and order data, "
            "then routes to the appropriate handler internally.",
    inputs=[
        {"name": "command", "type": "str",
         "description": "Order command: 'place' | 'cancel' | 'track'"},
        {"name": "order_data", "type": "dict",
         "description": "Order payload: items (list), payment_method (str), shipping_address (dict), order_id (str)"},
    ],
    outputs=[{"name": "order_result", "type": "dict",
              "description": "JSON with: success (bool), order_id (str), status (str), message (str)"}],
    global_vars=[
        {"variable": "orders", "op": "read_write",
         "description": "Dict mapping order_id to {items, payment, address, status, created_at}"},
        {"variable": "inventory", "op": "read_write",
         "description": "Dict mapping product_id to {stock_count, reserved_count, price}"},
        {"variable": "payments", "op": "read_write",
         "description": "Dict mapping payment_id to {order_id, amount, method, status}"},
    ],
    data_sources=[
        {"name": "orders", "description": "Order records storage"},
        {"name": "inventory", "description": "Product stock data"},
    ],
    subprd_desc=(
        "The OrderSystem function is called as: process_order(command, order_data)\n\n"
        "command determines which operation to perform:\n"
        "  - 'place': Validate items exist and have sufficient stock, charge payment via payment gateway, "
        "reserve inventory, create order record, send confirmation notification.\n"
        "  - 'cancel': Verify order exists and is not yet shipped, refund payment, restore inventory, "
        "update order status to cancelled.\n"
        "  - 'track': Return current order status and estimated delivery time.\n\n"
        "The function must handle all three commands through a single entry point. "
        "Internally, it should parse the command and delegate to the appropriate logic."
    ),
    subprd_constraints=[
        "All operations must be atomic: if any step fails, previous steps must be rolled back",
        "Inventory must be reserved (not decremented) until order is confirmed",
        "Payment must be charged before stock is decremented",
        "Cannot cancel a shipped order",
    ],
    subprd_acs=[
        {"ac_id": "AC-01", "description": "Placing an order with valid items and payment creates order and returns order_id"},
        {"ac_id": "AC-02", "description": "Placing an order with insufficient stock returns error without charging payment"},
        {"ac_id": "AC-03", "description": "Cancelling a pending order refunds payment and restores stock"},
        {"ac_id": "AC-04", "description": "Tracking an existing order returns its current status"},
    ],
    tags=["command_dispatch", "cross_resource", "atomic_operations"],
)


# =======================================================================
# Case 2: Chat Application (command-dispatch pattern)
# =======================================================================
CASE_02_CHAT = _make_case(
    node_id="root_chat", name="ChatApp",
    purpose="Handle real-time messaging operations via a single entry point. "
            "The function receives a command and message data, "
            "then routes to the appropriate handler.",
    inputs=[
        {"name": "command", "type": "str",
         "description": "Chat command: 'send' | 'history' | 'create_channel' | 'join'"},
        {"name": "message_data", "type": "dict",
         "description": "Message payload: content (str), channel_id (str), user_id (str), channel_name (str)"},
    ],
    outputs=[{"name": "message_result", "type": "dict",
              "description": "JSON with: success (bool), data (varies), message (str)"}],
    global_vars=[
        {"variable": "messages", "op": "read_write",
         "description": "Dict mapping message_id to {channel_id, user_id, content, timestamp}"},
        {"variable": "users", "op": "read",
         "description": "Dict mapping user_id to {username, status, last_seen}"},
        {"variable": "channels", "op": "read_write",
         "description": "Dict mapping channel_id to {name, members, created_by}"},
    ],
    data_sources=[
        {"name": "messages", "description": "Message store"},
        {"name": "channels", "description": "Channel data"},
    ],
    subprd_desc=(
        "The ChatApp function is called as: handle_chat(command, message_data)\n\n"
        "command determines which operation to perform:\n"
        "  - 'send': Validate user is a member of the target channel, store the message, "
        "update user's last_seen timestamp, notify other channel members.\n"
        "  - 'history': Retrieve the last 100 messages from a channel, sorted by timestamp descending.\n"
        "  - 'create_channel': Create a new channel with the given name, set the caller as creator and first member.\n"
        "  - 'join': Add the user to a channel's member list if not already a member.\n\n"
        "The function must handle all four commands through a single entry point."
    ),
    subprd_constraints=[
        "Users can only send messages to channels they have joined",
        "Message history is limited to the last 100 messages per channel",
        "Channel names must be unique",
        "A user cannot join a channel they are already a member of",
    ],
    subprd_acs=[
        {"ac_id": "AC-01", "description": "Sending a message to a joined channel stores it and returns success"},
        {"ac_id": "AC-02", "description": "Sending a message to a non-joined channel returns error"},
        {"ac_id": "AC-03", "description": "Retrieving history returns messages sorted by timestamp descending"},
        {"ac_id": "AC-04", "description": "Creating a channel makes the creator the first member"},
    ],
    tags=["command_dispatch", "membership_validation"],
)


# =======================================================================
# Case 3: CI/CD Build System (kept as-is — action-based, no routing)
# =======================================================================
CASE_03_BUILD = _make_case(
    node_id="root_build", name="BuildSystem",
    purpose="Manage CI/CD builds: trigger builds, check status, list build history, cancel running builds.",
    inputs=[{"name": "build_request", "type": "dict",
             "description": "JSON with: action (trigger/status/list/cancel), repo (str), branch (str), config (dict)"}],
    outputs=[{"name": "build_result", "type": "dict",
              "description": "JSON with: success (bool), build_id (str), status (str), logs (list)"}],
    global_vars=[
        {"variable": "builds", "op": "read_write",
         "description": "Dict mapping build_id to {repo, branch, status, started_at, finished_at, logs}"},
        {"variable": "artifacts", "op": "read_write",
         "description": "Dict mapping artifact_id to {build_id, path, size, created_at}"},
    ],
    data_sources=[{"name": "builds", "description": "Build records"}],
    subprd_desc=(
        "INPUT FORMAT: build_request is a JSON object.\n"
        "  - action: 'trigger' | 'status' | 'list' | 'cancel'\n"
        "  - repo: str (required for trigger), branch: str (default 'main')\n"
        "  - config: {build_steps: list of str} (required for trigger)\n"
        "  - build_id: str (required for status, cancel)\n\n"
        "BUSINESS RULES:\n"
        "  - trigger: create build record, run compile, run test, package artifacts, update status\n"
        "  - status: return current build status and logs\n"
        "  - list: return all builds filtered by repo/branch/status\n"
        "  - cancel: stop a running build, update status to 'cancelled'"
    ),
    subprd_constraints=[
        "Only one build per repo+branch can run at a time",
        "Build logs must be stored incrementally",
        "Cancelling a completed build is a no-op",
        "Build artifacts must be stored with the build record",
    ],
    subprd_acs=[
        {"ac_id": "AC-01", "description": "Triggering a build creates a record and returns build_id"},
        {"ac_id": "AC-02", "description": "Triggering a build while one is running for same repo+branch returns error"},
        {"ac_id": "AC-03", "description": "Cancelling a running build updates status to cancelled"},
        {"ac_id": "AC-04", "description": "Listing builds returns filtered results"},
    ],
    tags=["sequential_pipeline", "concurrency_control"],
)


# =======================================================================
# Case 4: Inventory Manager (command-dispatch pattern)
# =======================================================================
CASE_04_INVENTORY = _make_case(
    node_id="root_inventory", name="InventoryManager",
    purpose="Manage warehouse inventory via a single entry point. "
            "The function receives a command and item data, "
            "then routes to the appropriate handler.",
    inputs=[
        {"name": "command", "type": "str",
         "description": "Inventory command: 'add' | 'update' | 'check' | 'report'"},
        {"name": "item_data", "type": "dict",
         "description": "Item payload: product_id (str), name (str), quantity (int), reorder_threshold (int)"},
    ],
    outputs=[{"name": "inventory_result", "type": "dict",
              "description": "JSON with: success (bool), data (varies), message (str)"}],
    global_vars=[
        {"variable": "stock", "op": "read_write",
         "description": "Dict mapping product_id to {name, quantity, reorder_threshold, last_updated}"},
        {"variable": "suppliers", "op": "read",
         "description": "Dict mapping supplier_id to {name, products, lead_time_days}"},
        {"variable": "purchase_orders", "op": "read_write",
         "description": "Dict mapping po_id to {supplier_id, items, status, created_at}"},
    ],
    data_sources=[{"name": "stock", "description": "Stock levels"}],
    subprd_desc=(
        "The InventoryManager function is called as: manage_inventory(command, item_data)\n\n"
        "command determines which operation to perform:\n"
        "  - 'add': Validate product_id uniqueness, create a new stock record with initial quantity.\n"
        "  - 'update': Adjust stock quantity for a product. If quantity goes below reorder threshold, "
        "automatically create a purchase order to the appropriate supplier.\n"
        "  - 'check': Return current quantity and availability status for a product.\n"
        "  - 'report': Find all items below reorder threshold, suggest suppliers with lead time estimates.\n\n"
        "The function must handle all four commands through a single entry point."
    ),
    subprd_constraints=[
        "Stock quantity cannot go below zero",
        "Product IDs must be unique",
        "Reorder report must include supplier lead time estimates",
        "Stock updates must log the change timestamp",
    ],
    subprd_acs=[
        {"ac_id": "AC-01", "description": "Adding a new item creates a stock record"},
        {"ac_id": "AC-02", "description": "Updating stock below zero returns error"},
        {"ac_id": "AC-03", "description": "Checking availability returns current quantity"},
        {"ac_id": "AC-04", "description": "Report lists items below reorder threshold with supplier info"},
    ],
    tags=["command_dispatch", "threshold_trigger"],
)


# =======================================================================
# Case 5: Patient Portal (command-dispatch pattern)
# =======================================================================
CASE_05_PATIENT = _make_case(
    node_id="root_patient", name="PatientPortal",
    purpose="Manage patient healthcare operations via a single entry point. "
            "The function receives a command and patient data, "
            "then routes to the appropriate handler.",
    inputs=[
        {"name": "command", "type": "str",
         "description": "Patient command: 'register' | 'book' | 'records' | 'update'"},
        {"name": "patient_data", "type": "dict",
         "description": "Patient payload: name (str), dob (str), contact (str), insurance (dict), "
                        "patient_id (str), doctor_id (str), appointment_time (str)"},
    ],
    outputs=[{"name": "patient_result", "type": "dict",
              "description": "JSON with: success (bool), data (varies), message (str)"}],
    global_vars=[
        {"variable": "patients", "op": "read_write",
         "description": "Dict mapping patient_id to {name, dob, contact, insurance, registered_at}"},
        {"variable": "appointments", "op": "read_write",
         "description": "Dict mapping appointment_id to {patient_id, doctor_id, time, status, notes}"},
        {"variable": "records", "op": "read_write",
         "description": "Dict mapping record_id to {patient_id, type, data, created_by, timestamp}"},
    ],
    data_sources=[
        {"name": "patients", "description": "Patient records"},
        {"name": "appointments", "description": "Appointment records"},
    ],
    subprd_desc=(
        "The PatientPortal function is called as: handle_patient_request(command, patient_data)\n\n"
        "command determines which operation to perform:\n"
        "  - 'register': Validate required fields (name, dob, contact, insurance), "
        "create patient record, generate unique patient_id.\n"
        "  - 'book': Check patient exists, check doctor availability at requested time, "
        "create appointment record, send confirmation.\n"
        "  - 'records': Retrieve all medical records for a patient, sorted by date descending.\n"
        "  - 'update': Update patient profile fields. If insurance is changed, validate against external system.\n\n"
        "The function must handle all four commands through a single entry point."
    ),
    subprd_constraints=[
        "Patient must be registered before booking appointments",
        "Cannot book appointments in the past",
        "Medical records are append-only (cannot be modified)",
        "Insurance info must be validated against external system before saving",
    ],
    subprd_acs=[
        {"ac_id": "AC-01", "description": "Registering a patient creates a record and returns patient_id"},
        {"ac_id": "AC-02", "description": "Booking for unregistered patient returns error"},
        {"ac_id": "AC-03", "description": "Records retrieval returns sorted list"},
        {"ac_id": "AC-04", "description": "Updating insurance triggers validation"},
    ],
    tags=["command_dispatch", "cross_resource", "external_validation"],
)


# =======================================================================
# Case 6: Social Feed (command-dispatch pattern)
# =======================================================================
CASE_06_SOCIAL = _make_case(
    node_id="root_social", name="SocialFeed",
    purpose="Social media feed operations via a single entry point. "
            "The function receives a command and feed data, "
            "then routes to the appropriate handler.",
    inputs=[
        {"name": "command", "type": "str",
         "description": "Feed command: 'post' | 'feed' | 'like' | 'follow'"},
        {"name": "feed_data", "type": "dict",
         "description": "Feed payload: content (str), post_id (str), target_user_id (str), user_id (str)"},
    ],
    outputs=[{"name": "feed_result", "type": "dict",
              "description": "JSON with: success (bool), data (varies), message (str)"}],
    global_vars=[
        {"variable": "posts", "op": "read_write",
         "description": "Dict mapping post_id to {user_id, content, likes, timestamp}"},
        {"variable": "users", "op": "read_write",
         "description": "Dict mapping user_id to {username, followers, following}"},
        {"variable": "feed_cache", "op": "read_write",
         "description": "Dict mapping user_id to {feed, last_updated}"},
    ],
    data_sources=[{"name": "posts", "description": "Post records"}],
    subprd_desc=(
        "The SocialFeed function is called as: manage_feed(command, feed_data)\n\n"
        "command determines which operation to perform:\n"
        "  - 'post': Create a new post, invalidate feed caches of all followers.\n"
        "  - 'feed': Generate personalized feed from followed users' posts, ranked by recency and engagement.\n"
        "  - 'like': Add user to post's likes list, update engagement score.\n"
        "  - 'follow': Add target to user's following list, add user to target's followers list (bidirectional).\n\n"
        "The function must handle all four commands through a single entry point."
    ),
    subprd_constraints=[
        "Users cannot follow themselves",
        "Users cannot like the same post twice",
        "Feed cache must be invalidated when a followed user posts",
        "Feed is limited to 50 most recent posts",
    ],
    subprd_acs=[
        {"ac_id": "AC-01", "description": "Creating a post stores it and invalidates follower caches"},
        {"ac_id": "AC-02", "description": "Feed returns posts from followed users sorted by recency"},
        {"ac_id": "AC-03", "description": "Liking a post adds user to likes list"},
        {"ac_id": "AC-04", "description": "Following a user updates both following and followers lists"},
    ],
    tags=["command_dispatch", "cache_invalidation", "bidirectional_update"],
)


# =======================================================================
# Case 7: Task Planner (command-dispatch pattern)
# =======================================================================
CASE_07_TASK = _make_case(
    node_id="root_task", name="TaskPlanner",
    purpose="Project task management via a single entry point. "
            "The function receives a command and task data, "
            "then routes to the appropriate handler.",
    inputs=[
        {"name": "command", "type": "str",
         "description": "Task command: 'create' | 'assign' | 'progress' | 'overview'"},
        {"name": "task_data", "type": "dict",
         "description": "Task payload: title (str), description (str), project_id (str), "
                        "priority (str), task_id (str), assignee_id (str), status_update (str)"},
    ],
    outputs=[{"name": "task_result", "type": "dict",
              "description": "JSON with: success (bool), data (varies), message (str)"}],
    global_vars=[
        {"variable": "tasks", "op": "read_write",
         "description": "Dict mapping task_id to {title, description, status, assignee_id, project_id, priority}"},
        {"variable": "projects", "op": "read_write",
         "description": "Dict mapping project_id to {name, owner, task_ids, deadline}"},
        {"variable": "assignments", "op": "read_write",
         "description": "Dict mapping assignment_id to {task_id, assignee_id, assigned_at, status}"},
    ],
    data_sources=[{"name": "tasks", "description": "Task records"}],
    subprd_desc=(
        "The TaskPlanner function is called as: manage_task(command, task_data)\n\n"
        "command determines which operation to perform:\n"
        "  - 'create': Validate project exists, create task record, add to project's task list.\n"
        "  - 'assign': Validate assignee exists and task is not completed, create assignment record, update task.\n"
        "  - 'progress': Update task status following valid transitions (todo->in_progress->review->done). "
        "If task is completed, notify project owner.\n"
        "  - 'overview': Aggregate task counts by status for a project, calculate completion percentage, "
        "identify blocked tasks.\n\n"
        "The function must handle all four commands through a single entry point."
    ),
    subprd_constraints=[
        "Tasks must belong to a project",
        "Cannot assign a task that is already completed",
        "Overview must include blocked tasks count",
        "Status transitions must be valid (todo -> in_progress -> review -> done)",
    ],
    subprd_acs=[
        {"ac_id": "AC-01", "description": "Creating a task links it to a project"},
        {"ac_id": "AC-02", "description": "Assigning a completed task returns error"},
        {"ac_id": "AC-03", "description": "Progress update validates status transition"},
        {"ac_id": "AC-04", "description": "Overview returns accurate completion percentage"},
    ],
    tags=["command_dispatch", "status_machine", "cross_resource"],
)


# =======================================================================
# Case 8: Data Pipeline (ETL) (kept as-is — sequential, no routing)
# =======================================================================
CASE_08_PIPELINE = _make_case(
    node_id="root_pipeline", name="DataPipeline",
    purpose="ETL data processing: ingest raw data, apply transformations, validate quality, export results.",
    inputs=[{"name": "pipeline_request", "type": "dict",
             "description": "JSON with: action (ingest/transform/validate/export), source (dict), transform_config (dict)"}],
    outputs=[{"name": "pipeline_result", "type": "dict",
              "description": "JSON with: success (bool), records_processed (int), errors (list), data (list)"}],
    global_vars=[
        {"variable": "raw_data", "op": "read_write", "description": "List of raw records from source ingestion"},
        {"variable": "processed_data", "op": "read_write", "description": "List of transformed and validated records"},
        {"variable": "pipeline_log", "op": "read_write",
         "description": "List of {step, timestamp, records_in, records_out, errors}"},
    ],
    data_sources=[
        {"name": "raw_data", "description": "Raw ingested data"},
        {"name": "processed_data", "description": "Transformed data"},
    ],
    subprd_desc=(
        "INPUT FORMAT: pipeline_request is a JSON object.\n"
        "  - action: 'ingest' | 'transform' | 'validate' | 'export'\n"
        "  - source: {type: 'csv'|'json'|'api', path_or_url: str} (for ingest)\n"
        "  - transform_config: {rules: list of {field, operation, value}} (for transform)\n"
        "  - export_format: 'csv' | 'json' (for export)\n\n"
        "BUSINESS RULES:\n"
        "  - ingest: read from source, parse records, store in raw_data, log ingestion\n"
        "  - transform: apply transformation rules to raw_data, store in processed_data\n"
        "  - validate: check processed_data against quality rules, mark invalid records\n"
        "  - export: format processed_data as output, log export"
    ),
    subprd_constraints=[
        "Each step must log to pipeline_log with counts",
        "Transform must skip and log malformed records rather than failing",
        "Validate must produce a quality_score for each record",
        "Export must include only records that passed validation",
    ],
    subprd_acs=[
        {"ac_id": "AC-01", "description": "Ingesting data stores records in raw_data"},
        {"ac_id": "AC-02", "description": "Transform applies all rules and logs skipped records"},
        {"ac_id": "AC-03", "description": "Validate assigns quality_score to each record"},
        {"ac_id": "AC-04", "description": "Export includes only valid records"},
    ],
    tags=["sequential_pipeline", "error_tolerance"],
)


# =======================================================================
# Case 9: Notification Hub (command-dispatch pattern)
# =======================================================================
CASE_09_NOTIFICATION = _make_case(
    node_id="root_notification", name="NotificationHub",
    purpose="Multi-channel notification system via a single entry point. "
            "The function receives a command and notification data, "
            "then routes to the appropriate handler.",
    inputs=[
        {"name": "command", "type": "str",
         "description": "Notification command: 'send' | 'status' | 'template' | 'schedule'"},
        {"name": "notification_data", "type": "dict",
         "description": "Notification payload: type (email/sms/push), recipient (str), "
                        "content (dict), template_id (str), notification_id (str), schedule_time (str)"},
    ],
    outputs=[{"name": "notification_result", "type": "dict",
              "description": "JSON with: success (bool), notification_id (str), status (str), message (str)"}],
    global_vars=[
        {"variable": "notification_queue", "op": "read_write",
         "description": "Dict mapping notification_id to {type, recipient, content, status, scheduled_at, sent_at}"},
        {"variable": "templates", "op": "read",
         "description": "Dict mapping template_id to {name, body, channels}"},
        {"variable": "delivery_log", "op": "read_write",
         "description": "List of {notification_id, channel, status, timestamp, error_msg}"},
    ],
    data_sources=[{"name": "notification_queue", "description": "Notification queue"}],
    subprd_desc=(
        "The NotificationHub function is called as: send_notification(command, notification_data)\n\n"
        "command determines which operation to perform:\n"
        "  - 'send': Resolve template if template_id is provided, validate recipient format "
        "(email regex for email, phone format for SMS), queue notification, attempt immediate delivery.\n"
        "  - 'status': Return current delivery status for a notification_id.\n"
        "  - 'template': CRUD operations on templates (create, read, update, delete based on sub-action).\n"
        "  - 'schedule': Queue notification with a future scheduled_at time instead of immediate delivery.\n\n"
        "The function must handle all four commands through a single entry point."
    ),
    subprd_constraints=[
        "Email addresses must match email regex pattern",
        "Phone numbers must be valid international format for SMS",
        "Template variables must all be provided or have defaults",
        "Scheduled notifications cannot be in the past",
    ],
    subprd_acs=[
        {"ac_id": "AC-01", "description": "Sending an email notification queues it and attempts delivery"},
        {"ac_id": "AC-02", "description": "Sending with invalid email format returns error"},
        {"ac_id": "AC-03", "description": "Status check returns current delivery state"},
        {"ac_id": "AC-04", "description": "Scheduling a notification stores it with future timestamp"},
    ],
    tags=["command_dispatch", "multi_channel", "template_resolution"],
)


# =======================================================================
# Case 10: Booking Engine (kept as-is — action-based, no routing)
# =======================================================================
CASE_10_BOOKING = _make_case(
    node_id="root_booking", name="BookingEngine",
    purpose="Reservation system: make bookings, cancel bookings, check availability, list bookings.",
    inputs=[{"name": "booking_request", "type": "dict",
             "description": "JSON with: action (book/cancel/availability/list), resource_id (str), "
                            "time_range (dict with start, end), user_id (str)"}],
    outputs=[{"name": "booking_result", "type": "dict",
              "description": "JSON with: success (bool), booking_id (str), data (varies), message (str)"}],
    global_vars=[
        {"variable": "bookings", "op": "read_write",
         "description": "Dict mapping booking_id to {resource_id, user_id, start, end, status, created_at}"},
        {"variable": "resources", "op": "read",
         "description": "Dict mapping resource_id to {name, type, capacity, operating_hours}"},
        {"variable": "availability", "op": "read_write",
         "description": "Dict mapping resource_id to list of {start, end, booking_id}"},
    ],
    data_sources=[{"name": "bookings", "description": "Booking records"}],
    subprd_desc=(
        "INPUT FORMAT: booking_request is a JSON object.\n"
        "  - action: 'book' | 'cancel' | 'availability' | 'list'\n"
        "  - resource_id: str (for book, availability, list)\n"
        "  - time_range: {start: str ISO, end: str ISO} (for book, availability)\n"
        "  - user_id: str (for book, cancel), booking_id: str (for cancel)\n\n"
        "BUSINESS RULES:\n"
        "  - book: check resource exists, check time slot available (no overlap), create booking, update availability\n"
        "  - cancel: check booking exists and belongs to user, release time slot, update status\n"
        "  - availability: return all occupied and free slots for a resource in a date range\n"
        "  - list: return all bookings for a resource or user"
    ),
    subprd_constraints=[
        "Bookings cannot overlap for the same resource",
        "Cannot book outside resource operating hours",
        "Cancellation must release the time slot immediately",
        "Time ranges must have start < end",
    ],
    subprd_acs=[
        {"ac_id": "AC-01", "description": "Booking an available slot creates booking and updates availability"},
        {"ac_id": "AC-02", "description": "Booking an overlapping slot returns error"},
        {"ac_id": "AC-03", "description": "Cancelling a booking releases the time slot"},
        {"ac_id": "AC-04", "description": "Availability check returns accurate free/occupied slots"},
    ],
    tags=["time_slot_management", "overlap_detection"],
)


# =======================================================================
# Collection
# =======================================================================
ALL_CASES = [
    CASE_01_ORDER, CASE_02_CHAT, CASE_03_BUILD, CASE_04_INVENTORY,
    CASE_05_PATIENT, CASE_06_SOCIAL, CASE_07_TASK, CASE_08_PIPELINE,
    CASE_09_NOTIFICATION, CASE_10_BOOKING,
]


def get_cases():
    return ALL_CASES


def get_case(index):
    return ALL_CASES[index]
