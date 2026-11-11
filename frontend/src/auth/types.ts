export type User = {
  id: string;
  email: string;
  display_name: string | null;
  role: 'user' | 'admin' | 'superadmin';
  account_status: string;
  email_verified_at: string | null;
};

export type Session = {
  id: string;
  created_at: string;
  last_activity_at: string;
  expires_at: string;
  revoked_at: string | null;
  current: boolean;
};
