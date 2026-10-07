# Application configuration planned

Weeks 3 and 4 add a Podinfo Kustomize base and Pi overlay.
Use two replicas, ClusterIP Service, bundled Traefik Ingress, health probes,
requests/limits, an immutable ARM64 image reference, and proportionate security.

Keep platform namespaces, Roles, RoleBindings, and NetworkPolicies under platform/.
No application manifest has passed runtime verification yet.
