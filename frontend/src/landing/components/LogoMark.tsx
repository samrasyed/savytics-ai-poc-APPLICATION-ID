type Props = { size?: number; className?: string };

// Draws the Sift mark: four dots of falling size, like particles passing through a sieve.
export default function LogoMark({ size = 28, className }: Props) {
  return (
    <svg
      className={className}
      width={(size * 12) / 30}
      height={size}
      viewBox="0 0 12 30"
      aria-hidden="true"
      focusable="false"
    >
      <circle cx="6" cy="4" r="4" fill="var(--sift-pastel-butter)" />
      <circle cx="6" cy="13.25" r="3.25" fill="var(--sift-pastel-rose)" />
      <circle cx="6" cy="21" r="2.5" fill="var(--sift-pastel-mint)" />
      <circle cx="6" cy="27.25" r="1.75" fill="var(--sift-pastel-lavender)" />
    </svg>
  );
}
