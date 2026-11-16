import Link from 'next/link';

export function StoreFooter() {
  return (
    <footer className="border-border mt-16 border-t">
      <div className="mx-auto grid max-w-7xl gap-6 px-4 py-10 text-sm sm:grid-cols-3 sm:px-6">
        <div>
          <p className="font-semibold">CartIQ</p>
          <p className="text-muted-foreground mt-2">
            A demo storefront built to diagnose where shoppers drop off, ship interventions against
            it, and measure them honestly.
          </p>
        </div>
        <div>
          <p className="font-semibold">Project</p>
          <ul className="text-muted-foreground mt-2 space-y-1">
            <li>
              <Link href="/about" className="hover:text-foreground hover:underline">
                About this project
              </Link>
            </li>
            <li>
              <Link href="/console" className="hover:text-foreground hover:underline">
                Conversion intelligence console
              </Link>
            </li>
          </ul>
        </div>
        <div>
          <p className="font-semibold">Where the products come from</p>
          <p className="text-muted-foreground mt-2">
            Real transactions from the UCI <em>Online Retail II</em> dataset, used under CC BY 4.0.
            Titles and prices are real; categories are derived. No product imagery exists in the
            source, so every image here is a placeholder.
          </p>
        </div>
      </div>
    </footer>
  );
}
