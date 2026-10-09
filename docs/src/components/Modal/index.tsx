import {useEffect, useId, useRef, useState, type ReactNode} from 'react';
import {createPortal} from 'react-dom';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import styles from './styles.module.css';

type DialogProps = {
  title: ReactNode;
  children: ReactNode;
  href?: string;
  hrefLabel?: string;
  wide?: boolean;
  onClose: () => void;
};

/** A native modal <dialog>, portalled to <body> so triggers can sit inside a paragraph. */
function Dialog({title, children, href, hrefLabel, wide, onClose}: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    // Unmounting removes the dialog from the top layer, so there is nothing to clean up.
    if (ref.current && !ref.current.open) {
      ref.current.showModal();
    }
  }, []);

  return createPortal(
    <dialog
      ref={ref}
      className={clsx(styles.dialog, wide && styles.wide)}
      aria-labelledby={titleId}
      onClose={onClose}
      // The panel fills the dialog, so a click that lands on the dialog itself is on the backdrop.
      onClick={(event) => event.target === ref.current && ref.current?.close()}>
      <div className={styles.panel}>
        <div className={styles.header}>
          <h3 id={titleId} className={styles.title}>
            {title}
          </h3>
          <button
            type="button"
            className={styles.close}
            aria-label="Close"
            onClick={() => ref.current?.close()}>
            ×
          </button>
        </div>
        <div className={styles.body}>{children}</div>
        {href && (
          <div className={styles.footer}>
            <Link to={href} onClick={() => ref.current?.close()}>
              {hrefLabel ?? 'Read more'} →
            </Link>
          </div>
        )}
      </div>
    </dialog>,
    document.body,
  );
}

type ModalProps = {
  /** What the reader clicks. */
  trigger: ReactNode;
  title: ReactNode;
  children: ReactNode;
  href?: string;
  hrefLabel?: string;
  /**
   * "button" for a standalone button, "term" for an inline underlined word,
   * "card" for a grid card, "figure" for a thumbnail image.
   */
  variant?: 'button' | 'term' | 'card' | 'figure';
  /** Open a wider dialog, for screenshots and recordings. */
  wide?: boolean;
  className?: string;
};

/**
 * A button that opens a modal. In MDX, leave a blank line after the opening
 * tag so the children are parsed as Markdown:
 *
 *   <Modal trigger="Show the full config" title="Full config">
 *
 *   ...markdown...
 *
 *   </Modal>
 */
export default function Modal({
  trigger,
  title,
  children,
  href,
  hrefLabel,
  variant = 'button',
  wide = false,
  className,
}: ModalProps) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        className={clsx(styles.trigger, styles[variant], className)}
        aria-haspopup="dialog"
        onClick={() => setOpen(true)}>
        {trigger}
      </button>
      {open && (
        <Dialog
          title={title}
          href={href}
          hrefLabel={hrefLabel}
          wide={wide}
          onClose={() => setOpen(false)}>
          {children}
        </Dialog>
      )}
    </>
  );
}
