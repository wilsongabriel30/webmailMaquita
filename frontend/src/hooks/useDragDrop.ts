/**
 * MessageList_dragdrop.patch.ts
 *
 * Drag-and-drop support for moving messages between folders.
 * Provides two hooks:
 *   - useDragMessage(): attach to message rows to make them draggable
 *   - useFolderDrop():  attach to folder tree items to accept drops
 *
 * Integration:
 *   In MessageList.tsx, spread `onDragStart` onto each message <div>.
 *   In FolderTree.tsx, spread the drop handlers onto each folder <li>.
 */

import { useState, useCallback, useRef } from 'react';

// ─── Drag Source (message rows) ─────────────────────────────────────────────

export interface DragMessageHandlers {
  onDragStart: (e: React.DragEvent, uid: number, subject: string) => void;
  onDragEnd: (e: React.DragEvent) => void;
  draggingUid: number | null;
}

export function useDragMessage(): DragMessageHandlers {
  const [draggingUid, setDraggingUid] = useState<number | null>(null);

  const onDragStart = useCallback(
    (e: React.DragEvent, uid: number, subject: string) => {
      e.dataTransfer.setData('text/plain', String(uid));
      e.dataTransfer.setData('application/x-mail-uid', String(uid));
      e.dataTransfer.effectAllowed = 'move';

      // Build a lightweight drag image so the user sees context while dragging
      const ghost = document.createElement('div');
      ghost.textContent = subject.length > 60 ? subject.slice(0, 57) + '...' : subject;
      ghost.style.cssText = [
        'position:absolute',
        'top:-1000px',
        'left:0',
        'padding:6px 12px',
        'background:#0078d4',
        'color:#fff',
        'font-family:Calibri,sans-serif',
        'font-size:13px',
        'border-radius:3px',
        'white-space:nowrap',
        'pointer-events:none',
        'box-shadow:0 2px 6px rgba(0,0,0,.25)',
      ].join(';');
      document.body.appendChild(ghost);
      e.dataTransfer.setDragImage(ghost, 0, 0);

      // Clean up the ghost after the browser has captured it
      requestAnimationFrame(() => {
        document.body.removeChild(ghost);
      });

      setDraggingUid(uid);
    },
    [],
  );

  const onDragEnd = useCallback((_e: React.DragEvent) => {
    setDraggingUid(null);
  }, []);

  return { onDragStart, onDragEnd, draggingUid };
}

// ─── Drop Target (folder items) ─────────────────────────────────────────────

export interface FolderDropHandlers {
  /** True while a dragged message is hovering over this folder */
  isOver: boolean;
  onDragOver: (e: React.DragEvent) => void;
  onDragLeave: (e: React.DragEvent) => void;
  onDrop: (e: React.DragEvent) => void;
}

/**
 * Makes a folder a valid drop target for messages.
 *
 * @param folderName  IMAP folder path (e.g. "INBOX", "Drafts", "Archive")
 * @param onDrop      Callback invoked with the UIDs that were dropped and the
 *                    destination folder name.
 */
export function useFolderDrop(
  folderName: string,
  onDrop: (uids: number[], destFolder: string) => void,
): FolderDropHandlers {
  const [isOver, setIsOver] = useState(false);
  const dragCounter = useRef(0);

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    // Only set isOver on first enter to avoid flicker from child elements
    if (dragCounter.current === 0) {
      setIsOver(true);
    }
    dragCounter.current += 1;
  }, []);

  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    dragCounter.current -= 1;
    if (dragCounter.current <= 0) {
      dragCounter.current = 0;
      setIsOver(false);
    }
  }, []);

  const onDropHandler = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      dragCounter.current = 0;
      setIsOver(false);

      const raw = e.dataTransfer.getData('application/x-mail-uid');
      if (!raw) return;

      const uid = parseInt(raw, 10);
      if (isNaN(uid)) return;

      onDrop([uid], folderName);
    },
    [folderName, onDrop],
  );

  return {
    isOver,
    onDragOver,
    onDragLeave,
    onDrop: onDropHandler,
  };
}

// ─── Utility: CSS classes for visual feedback ───────────────────────────────

/** Returns Tailwind classes to apply on the folder element when a drag is over it. */
export function folderDropClasses(isOver: boolean): string {
  if (!isOver) return '';
  return 'bg-[#deecf9] border border-dashed border-[#0078d4] rounded';
}

/** Returns Tailwind classes to dim the message row being dragged. */
export function draggingRowClasses(isDragging: boolean): string {
  if (!isDragging) return '';
  return 'opacity-40';
}
