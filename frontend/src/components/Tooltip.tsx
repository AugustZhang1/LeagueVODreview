import {
  FloatingPortal,
  autoUpdate,
  flip,
  offset,
  shift,
  useDismiss,
  useFloating,
  useFocus,
  useHover,
  useInteractions,
  useRole,
} from "@floating-ui/react";
import { cloneElement, useState, type ReactElement, type ReactNode } from "react";
import styles from "./Tooltip.module.css";

type Props = {
  content: ReactNode;
  children: ReactElement<Record<string, unknown>>;
};

export function Tooltip({ content, children }: Props) {
  const [open, setOpen] = useState(false);
  const [reference, setReference] = useState<Element | null>(null);
  const [floating, setFloating] = useState<HTMLElement | null>(null);
  const { floatingStyles, context } = useFloating({
    elements: { reference, floating },
    open,
    onOpenChange: setOpen,
    placement: "top",
    whileElementsMounted: autoUpdate,
    middleware: [offset(6), flip(), shift({ padding: 8 })],
  });
  const { getReferenceProps, getFloatingProps } = useInteractions([
    useHover(context, { move: false, delay: { open: 150, close: 0 } }),
    useFocus(context),
    useDismiss(context),
    useRole(context, { role: "tooltip" }),
  ]);

  return (
    <>
      {cloneElement(children, getReferenceProps({ ref: setReference, ...children.props }))}
      {open && (
        <FloatingPortal>
          <div
            ref={setFloating}
            style={floatingStyles}
            className={styles.tooltip}
            {...getFloatingProps()}
          >
            {content}
          </div>
        </FloatingPortal>
      )}
    </>
  );
}
