import { createContext, useContext } from "react";

export interface AdminUser {
  id: number;
  username: string;
  display_name: string;
  role: string;
}

export interface AuthContextType {
  user: AdminUser | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextType>({
  user: null,
  login: async () => {},
  logout: () => {},
});

export const useAuth = () => useContext(AuthContext);
