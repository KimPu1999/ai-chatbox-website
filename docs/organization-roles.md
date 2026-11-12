# Organization roles

| Role | Read | Create chat | Manage members | Manage knowledge | Usage/audit |
|---|---:|---:|---:|---:|---:|
| owner | yes | yes | yes | yes | yes |
| admin | yes | yes | yes | yes | yes |
| member | yes | yes | no | no | no |
| viewer | yes | no | no | no | no |

The backend enforces this matrix. The last active owner cannot be suspended,
demoted, or removed. A member cannot change their own role. Platform
superadmin status does not grant ordinary workspace membership.

