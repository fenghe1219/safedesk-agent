import type { Metadata } from "next";

import { AccessDenied } from "@/components/access-denied";
import { EvaluationsConsole } from "@/components/evaluations-console";
import { can, requireMe } from "@/lib/page-guard";
import { getEvalDatasets, getEvalPrompts, getEvalRuns } from "@/lib/server-api";

export const metadata: Metadata = { title: "评估" };

export default async function EvaluationsPage() {
  const me = await requireMe();
  if (!can(me, "eval:manage")) {
    return <AccessDenied me={me} detail="当前角色没有进入评估控制台的权限。" />;
  }

  const [datasets, runs, prompts] = await Promise.all([
    getEvalDatasets(),
    getEvalRuns(),
    getEvalPrompts()
  ]);
  return (
    <EvaluationsConsole
      initialDatasets={datasets.items}
      initialRuns={runs.items}
      prompts={prompts}
      csrfToken={me.csrf_token}
    />
  );
}
