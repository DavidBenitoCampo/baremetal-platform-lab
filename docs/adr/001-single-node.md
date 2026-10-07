# ADR 001 One K3s server

Status: accepted project design. Runtime deployment pending.

Use one K3s server with the default SQLite datastore on the existing Pi.
The four hour weekly limit and fixed hardware favor a small operational lab.

The finished project should demonstrate releases, diagnosis, drift correction,
alerting, and a scoped restore. Two app Pods share one physical failure domain.
Pi failure stops both Pods and all local monitoring.

Future production design needs independent hosts, spare capacity, redundant
routing, durable application storage, and independent monitoring. These remain
outside the demonstrated lab.
