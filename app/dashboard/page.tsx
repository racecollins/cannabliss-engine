import { getDashboardData } from "@/data/dashboard/liveSpotify";

import { DashboardView } from "./_components/dashboard-view";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const { data, status } = await getDashboardData();

  return <DashboardView dashboardData={data} dashboardDataStatus={status} />;
}
