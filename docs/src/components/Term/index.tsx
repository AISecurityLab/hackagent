import type {ReactNode} from 'react';
import Modal from '@site/src/components/Modal';
import {TERMS} from '@site/src/components/Glossary/terms';

/**
 * An inline concept that opens its glossary definition:
 *   A <Term id="judge">judge</Term> scores each reply.
 * Without children it shows the concept's title.
 */
export default function Term({id, children}: {id: string; children?: ReactNode}) {
  const entry = TERMS[id];
  if (!entry) {
    throw new Error(`Unknown glossary term "${id}". Add it to src/components/Glossary/terms.tsx.`);
  }
  return (
    <Modal
      variant="term"
      trigger={children ?? entry.title}
      title={entry.title}
      href={entry.href}
      hrefLabel={entry.hrefLabel}>
      <p>{entry.summary}</p>
      {entry.body}
    </Modal>
  );
}
