import type { Role } from "./types";

export const DEMO_PASSWORD = "Demo123!";

export interface DemoAccount {
  role: Role;
  label: string;
  name: string;
  email: string;
  department: string;
}

export const DEMO_ACCOUNTS: DemoAccount[] = [
  { role: "employee", label: "员工", name: "林晓", email: "lin.xiao@example.test", department: "产品部" },
  { role: "support", label: "支持专员", name: "王工", email: "wang.gong@example.test", department: "桌面支持" },
  { role: "approver", label: "审批人", name: "陈审批", email: "chen.shenpi@example.test", department: "IT 安全" },
  { role: "admin", label: "管理员", name: "管理员", email: "admin@example.test", department: "IT 管理" },
  { role: "evaluator", label: "评估员", name: "评估员", email: "eval@example.test", department: "质量与评估" },
  { role: "auditor", label: "审计员", name: "审计员", email: "audit@example.test", department: "内审" }
];

export const ROLE_OPTIONS = DEMO_ACCOUNTS.map(({ role, label }) => ({ role, label }));
