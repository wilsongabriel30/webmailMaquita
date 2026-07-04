import { createContext, useContext } from "react";

export interface AdminUser {
  id: number;
  username: string;
  display_name: string;
  role: string;
}

export interface AuthContextType {
  user: AdminUser | null;
  // Devuelve { requires_totp: true } cuando la cuenta tiene 2FA y falta el código
  login: (username: string, password: string, totpCode?: string) => Promise<{ requires_totp?: boolean } | void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextType>({
  user: null,
  login: async () => {},
  logout: () => {},
});

export const useAuth = () => useContext(AuthContext);
