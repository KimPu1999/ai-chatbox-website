# Team invitations

Invitation tokens use 256 bits of random entropy and only their SHA-256 digest
is stored. They expire, are single use, are matched to the normalized email of
the verified account, and are accepted under a row lock. Development responses
may return the token for local testing; production responses omit it and the
configured mail service must deliver the link.

