import psycopg2
import uuid

conn = psycopg2.connect("postgresql://healmesh:healmesh_local@localhost:5432/healmesh")
conn.autocommit = True
cur = conn.cursor()

# Insert incident
inc_id = str(uuid.uuid4())
cur.execute("INSERT INTO healmesh.incidents (id, pod_name, namespace, failure_type, raw_payload, detected_at) VALUES (%s, 'test-pod', 'default', 'CrashLoopBackOff', '{}', NOW())", (inc_id,))

# Insert diagnosis
diag_id = str(uuid.uuid4())
cur.execute("INSERT INTO healmesh.diagnoses (id, incident_id, root_cause, confidence, raw_llm_response, prompt_snapshot, llm_model) VALUES (%s, %s, 'test cause', 'high', '{}', 'test', 'test')", (diag_id, inc_id))

# Insert action
action_id = str(uuid.uuid4())
cur.execute("INSERT INTO healmesh.actions (id, diagnosis_id, action_type, parse_status) VALUES (%s, %s, 'SCALE', 'parsed_ok')", (action_id, diag_id))

# Insert approval
approval_id = str(uuid.uuid4())
cur.execute("INSERT INTO healmesh.approvals (id, action_id, decision, approver_id, approver_name, decided_at) VALUES (%s, %s, 'approved', 'U12345', 'Test User', NOW())", (approval_id, action_id))

print(approval_id)
