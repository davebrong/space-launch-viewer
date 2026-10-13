import type { Metadata } from 'next';
import './style.css';
export const metadata: Metadata = { title: 'Launchlight — your sky, honestly', description: 'Evidence-based Cape launch viewing opportunities, local sunlight and NWS clouds.' };
export default function Layout({ children }: { children: React.ReactNode }) {
  return <html lang="en" data-scroll-behavior="smooth"><body>{children}</body></html>;
}
