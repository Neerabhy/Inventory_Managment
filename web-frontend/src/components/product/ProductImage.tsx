import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

const FALLBACK_PRODUCT_IMG: Record<string, string> = {
  Laptops: "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=400",
  Smartphones: "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=400",
  Headphones: "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=400",
  Monitors: "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=400",
  Tablets: "https://images.unsplash.com/photo-1561154464-82e9adf32764?w=400",
  Cameras: "https://images.unsplash.com/photo-1502920917128-1aa500764cbd?w=400",
  Speakers: "https://images.unsplash.com/photo-1545454675-3531b543be5d?w=400",
  Wearables: "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=400",
};

const DEFAULT_PRODUCT_IMG = FALLBACK_PRODUCT_IMG.Laptops;

export function productFallbackImage(category?: string | null) {
  return FALLBACK_PRODUCT_IMG[category ?? ""] ?? DEFAULT_PRODUCT_IMG;
}

type ProductImageProps = {
  src?: string | null;
  category?: string | null;
  alt: string;
  className?: string;
};

export function ProductImage({ src, category, alt, className }: ProductImageProps) {
  const fallback = productFallbackImage(category);
  const initialSrc = src?.trim() || fallback;
  const [currentSrc, setCurrentSrc] = useState(initialSrc);

  useEffect(() => {
    setCurrentSrc(src?.trim() || fallback);
  }, [fallback, src]);

  return (
    <img
      src={currentSrc}
      alt={alt}
      className={cn("bg-white object-contain", className)}
      onError={() => {
        if (currentSrc !== fallback) {
          setCurrentSrc(fallback);
        }
      }}
    />
  );
}
