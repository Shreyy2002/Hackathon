import { create } from "zustand";

export interface User {
  id: string;
  name: string;
  role: "employee" | "manager" | "hr";
  manager_id: string | null;
}

interface UserStore {
  currentUser: User | null;
  setUser: (user: User) => void;
}

export const useUserStore = create<UserStore>((set) => ({
  currentUser: null,
  setUser: (user: User) => set({ currentUser: user }),
}));
