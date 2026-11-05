// An internal link that switches view without reloading the page.

import type { AnchorHTMLAttributes, MouseEvent } from "react";
import { navigate } from "../router";

export function Link({ href, onClick, children, ...rest }: AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) {
  const go = (event: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(event);
    if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
    event.preventDefault();
    navigate(href);
    window.scrollTo(0, 0);
  };
  return (
    <a href={href} onClick={go} {...rest}>
      {children}
    </a>
  );
}
