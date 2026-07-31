"use client";

import { List, MagnifyingGlass, User } from "@phosphor-icons/react";
import Link from "next/link";
import type { FormEvent, ReactNode } from "react";
import { buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface AppTopBarProps {
  onOpenMobileNav: () => void;
  mobileNavOpen?: boolean;
  notificationSlot: ReactNode;
  profileHref: string;
  /** Post search — only rendered on the channel feed. */
  search?: {
    value: string;
    onChange: (value: string) => void;
    onSubmit: (event?: FormEvent) => void;
    placeholder?: string;
  };
}

export function AppTopBar({
  onOpenMobileNav,
  mobileNavOpen = false,
  notificationSlot,
  profileHref,
  search,
}: Readonly<AppTopBarProps>) {
  return (
    <header className="flex h-14 items-center gap-3 border-b border-border bg-background px-3 sm:h-16 sm:px-6">
      <button
        type="button"
        className={cn(
          buttonVariants({ variant: "outline", size: "icon" }),
          "size-10 shrink-0 rounded-[10px] border-border bg-transparent lg:hidden"
        )}
        aria-label="Open navigation"
        aria-expanded={mobileNavOpen}
        onClick={onOpenMobileNav}
      >
        <List className="size-5" weight="bold" />
      </button>

      {search ? (
        <form className="mx-auto flex w-full max-w-xl flex-1" onSubmit={search.onSubmit}>
          <div className="relative w-full">
            <label htmlFor="app-global-search" className="sr-only">
              Search posts
            </label>
            <MagnifyingGlass
              className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden
            />
            <Input
              id="app-global-search"
              value={search.value}
              onChange={(event) => search.onChange(event.target.value)}
              placeholder={search.placeholder ?? "Search posts"}
              className="h-10 rounded-xl border-border bg-secondary pl-9 text-foreground placeholder:text-muted-foreground"
            />
          </div>
        </form>
      ) : (
        <div className="flex-1" aria-hidden />
      )}

      <div className="flex shrink-0 items-center gap-2">
        {notificationSlot}
        <Link
          href={profileHref}
          aria-label="Open profile"
          className={cn(
            buttonVariants({ variant: "secondary", size: "icon" }),
            "size-10 rounded-[10px]"
          )}
        >
          <User className="size-5" weight="fill" />
        </Link>
      </div>
    </header>
  );
}
