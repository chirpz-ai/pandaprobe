import { SkeletonStatGrid, SkeletonTable } from "@/components/ui/Skeleton";

export default function OrgLoading() {
  return (
    <div className="space-y-6 animate-fade-in">
      <SkeletonStatGrid />
      <SkeletonTable rows={6} cols={4} />
    </div>
  );
}
