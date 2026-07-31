import Image from "next/image";
import { cn } from "@/lib/utils";

const SIZE_PX = {
  sm: 28,
  md: 40,
  lg: 56,
} as const;

interface ConveBrandMarkProps {
  readonly size?: keyof typeof SIZE_PX;
  readonly showWordmark?: boolean;
  readonly className?: string;
  readonly priority?: boolean;
}

export function ConveBrandMark({
  size = "md",
  showWordmark = true,
  className,
  priority = false,
}: ConveBrandMarkProps) {
  const px = SIZE_PX[size];

  return (
    <span className={cn("inline-flex items-center gap-2.5 text-foreground", className)}>
      <Image
        src="/conve-logo.png"
        alt=""
        width={px}
        height={px}
        className="shrink-0 rounded-[22%] [image-rendering:pixelated]"
        style={{ width: px, height: px }}
        priority={priority}
        unoptimized
        aria-hidden
      />
      {showWordmark ? (
        <span className="text-lg font-semibold tracking-tight">Conve</span>
      ) : (
        <span className="sr-only">Conve</span>
      )}
    </span>
  );
}
