import type {ReactNode} from 'react';
import useBaseUrl from '@docusaurus/useBaseUrl';
import Modal from '@site/src/components/Modal';
import styles from './styles.module.css';

type ScreenshotProps = {
  /** Site path of the image, e.g. /img/dashboard/runs.png. */
  src: string;
  alt: string;
  title: string;
  /** Shown in the modal under the full-size image. */
  children?: ReactNode;
};

/** A thumbnail that opens the full-size screenshot in a modal. */
export default function Screenshot({src, alt, title, children}: ScreenshotProps) {
  const url = useBaseUrl(src);
  return (
    <Modal
      variant="figure"
      wide
      title={title}
      trigger={
        <>
          <img className={styles.thumb} src={url} alt={alt} loading="lazy" />
          <span className={styles.caption}>{title}</span>
        </>
      }>
      <img className={styles.full} src={url} alt={alt} />
      {children}
    </Modal>
  );
}

/** Lays screenshots out in a responsive grid. */
export function ScreenshotGrid({children}: {children: ReactNode}) {
  return <div className={styles.grid}>{children}</div>;
}
