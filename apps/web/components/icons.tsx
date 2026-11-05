import type { SVGProps } from "react";

export type IconName =
  | "workbench"
  | "ticket"
  | "shield"
  | "book"
  | "flask"
  | "audit"
  | "chart"
  | "settings"
  | "arrow-right"
  | "check"
  | "clock"
  | "alert"
  | "document"
  | "logout"
  | "user"
  | "lock"
  | "search"
  | "branch"
  | "spark"
  | "plus"
  | "close"
  | "chevron-down";

interface IconProps extends SVGProps<SVGSVGElement> {
  name: IconName;
  size?: number;
}

export function Icon({ name, size = 16, className, ...props }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
      {...props}
    >
      {name === "workbench" && (
        <>
          <rect x="3.5" y="3.5" width="7" height="7" rx="1.5" />
          <rect x="13.5" y="3.5" width="7" height="7" rx="1.5" />
          <rect x="3.5" y="13.5" width="7" height="7" rx="1.5" />
          <rect x="13.5" y="13.5" width="7" height="7" rx="1.5" />
        </>
      )}
      {name === "ticket" && (
        <>
          <path d="M4 6.5h16v11H4z" />
          <path d="M8 6.5v11M8 11h5M8 14h3" />
        </>
      )}
      {name === "shield" && <path d="M12 3l7 3v5c0 4.4-3 8.2-7 9-4-.8-7-4.6-7-9V6l7-3z" />}
      {name === "book" && (
        <>
          <path d="M4 5.5A2.5 2.5 0 016.5 3H11v17H6.5A2.5 2.5 0 004 22V5.5z" />
          <path d="M20 5.5A2.5 2.5 0 0017.5 3H13v17h4.5A2.5 2.5 0 0120 22V5.5z" />
        </>
      )}
      {name === "flask" && (
        <>
          <path d="M9 3h6M10 3v6l-5 9a2 2 0 001.7 3h10.6a2 2 0 001.7-3l-5-9V3" />
          <path d="M7.5 15h9" />
        </>
      )}
      {name === "audit" && (
        <>
          <path d="M6 3.5h8l4 4V20H6z" />
          <path d="M14 3.5V8h4M9 13l2 2 4-4" />
        </>
      )}
      {name === "chart" && (
        <>
          <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
        </>
      )}
      {name === "settings" && (
        <>
          <circle cx="12" cy="12" r="3" />
          <path d="M12 2.8v2M12 19.2v2M2.8 12h2M19.2 12h2M5.5 5.5l1.4 1.4M17.1 17.1l1.4 1.4M18.5 5.5l-1.4 1.4M6.9 17.1l-1.4 1.4" />
        </>
      )}
      {name === "arrow-right" && <path d="M5 12h13M13 6.5l5.5 5.5L13 17.5" />}
      {name === "check" && <path d="M5 12.5l4.2 4L19 7" />}
      {name === "clock" && (
        <>
          <circle cx="12" cy="12" r="8" />
          <path d="M12 7.5V12l3 2" />
        </>
      )}
      {name === "alert" && (
        <>
          <path d="M12 4l8.5 15h-17L12 4z" />
          <path d="M12 9v4.5" />
          <circle cx="12" cy="16.2" r="0.7" fill="currentColor" stroke="none" />
        </>
      )}
      {name === "document" && (
        <>
          <path d="M7 3.5h7l4 4V20H7z" />
          <path d="M14 3.5V8h4M9.5 12h5M9.5 15.5h5" />
        </>
      )}
      {name === "logout" && (
        <>
          <path d="M10 4H5v16h5M14 8l4 4-4 4M8 12h10" />
        </>
      )}
      {name === "user" && (
        <>
          <circle cx="12" cy="8.5" r="3.2" />
          <path d="M5.5 19c.8-3 3.2-4.7 6.5-4.7s5.7 1.7 6.5 4.7" />
        </>
      )}
      {name === "lock" && (
        <>
          <rect x="5.5" y="10" width="13" height="9.5" rx="2" />
          <path d="M8.5 10V7.5a3.5 3.5 0 017 0V10" />
        </>
      )}
      {name === "search" && (
        <>
          <circle cx="10.5" cy="10.5" r="5.5" />
          <path d="M15 15l4.5 4.5" />
        </>
      )}
      {name === "branch" && (
        <>
          <circle cx="6" cy="5" r="2" />
          <circle cx="18" cy="7" r="2" />
          <circle cx="6" cy="19" r="2" />
          <path d="M6 7v10M8 8.5c2.5 0 3.5-1.5 5-3.5 1-1.3 2.3-1 3 0" />
        </>
      )}
      {name === "spark" && <path d="M12 3l1.6 5.4L19 10l-5.4 1.6L12 17l-1.6-5.4L5 10l5.4-1.6L12 3z" />}
      {name === "plus" && <path d="M12 5v14M5 12h14" />}
      {name === "close" && <path d="M6 6l12 12M18 6L6 18" />}
      {name === "chevron-down" && <path d="M6 9l6 6 6-6" />}
    </svg>
  );
}
