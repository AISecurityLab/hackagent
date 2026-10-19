import Modal from '@site/src/components/Modal';
import {TERMS} from '@site/src/components/Glossary/terms';
import styles from './styles.module.css';

/** Cards for glossary concepts; each card opens the concept's details. */
export default function ConceptGrid({ids}: {ids: string[]}) {
  return (
    <ul className={styles.grid}>
      {ids.map((id) => {
        const entry = TERMS[id];
        if (!entry) {
          throw new Error(`Unknown glossary term "${id}". Add it to src/components/Glossary/terms.tsx.`);
        }
        return (
          <li key={id} className={styles.item}>
            <Modal
              variant="card"
              title={entry.title}
              href={entry.href}
              hrefLabel={entry.hrefLabel}
              trigger={
                <>
                  <span className={styles.cardTitle}>{entry.title}</span>
                  <span className={styles.cardSummary}>{entry.summary}</span>
                </>
              }>
              <p>{entry.summary}</p>
              {entry.body}
            </Modal>
          </li>
        );
      })}
    </ul>
  );
}
