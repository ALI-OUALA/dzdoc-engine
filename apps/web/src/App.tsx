import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { Skeleton } from "@/components/ui/skeleton";

const LandingPage = lazy(() => import("@/pages/LandingPage").then((module) => ({ default: module.LandingPage })));
const PlatformPage = lazy(() => import("@/pages/PlatformPage").then((module) => ({ default: module.PlatformPage })));

export default function App() {
  return (
    <>
      <Suspense fallback={<main className="route-loading" aria-label="Loading page"><Skeleton className="h-8 w-36" /><Skeleton className="h-[60dvh] w-full" /></main>}>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/app" element={<PlatformPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
      <Toaster position="bottom-right" />
    </>
  );
}
