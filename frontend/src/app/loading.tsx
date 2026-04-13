import { Spinner } from "@/components/ui/Spinner";

export default function RootLoading() {
  return (
    <div className="flex h-screen w-full items-center justify-center bg-bg">
      <Spinner size="lg" />
    </div>
  );
}
