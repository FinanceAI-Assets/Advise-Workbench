import Image from "next/image";

// Deloitte wordmark in the application title area, with the product name beneath.
export function BrandMark({ id }: { id?: string }) {
  return (
    <div id={id} className="text-sm">
      <Image src="/brand/deloitte-logo.png" alt="Deloitte" width={103} height={22} priority />
      <p className="mt-1 text-2xs font-semibold uppercase tracking-wide text-[var(--primary-600)]">Advise Workbench</p>
    </div>
  );
}
