import DOMPurify from 'dompurify';

/**
 * Sanitize HTML using DOMPurify as defense-in-depth layer.
 * Backend already sanitizes with nh3 (Rust), this is the 2nd barrier.
 */
export function sanitizeHtml(dirty: string): string {
  return DOMPurify.sanitize(dirty, {
    ALLOWED_TAGS: [
      'a', 'b', 'blockquote', 'br', 'code', 'div', 'em', 'h1', 'h2', 'h3',
      'h4', 'h5', 'h6', 'hr', 'i', 'img', 'li', 'ol', 'p', 'pre', 's',
      'small', 'span', 'strong', 'table', 'tbody', 'td', 'tfoot', 'th',
      'thead', 'tr', 'u', 'ul', 'sub', 'sup', 'center', 'font',
      // col/colgroup (05/11/2026): anchos de columna de tablas de Excel/Outlook; nh3 ya los admite.
      'col', 'colgroup',
    ],
    ALLOWED_ATTR: [
      'href', 'src', 'alt', 'title', 'width', 'height', 'style', 'class',
      'id', 'target', 'rel', 'colspan', 'rowspan', 'align', 'valign',
      'border', 'cellpadding', 'cellspacing', 'bgcolor', 'color', 'size',
      'face', 'dir', 'lang', 'span',
    ],
    ALLOW_DATA_ATTR: false,
    ADD_ATTR: ['target'],
    FORBID_TAGS: ['script', 'style', 'iframe', 'object', 'embed', 'form', 'input', 'textarea', 'select', 'button'],
    FORBID_ATTR: ['onerror', 'onload', 'onclick', 'onmouseover', 'onfocus', 'onblur'],
  });
}

/**
 * Sanitize for signature/disclaimer previews (more permissive for styling).
 */
export function sanitizeSignatureHtml(dirty: string): string {
  return DOMPurify.sanitize(dirty, {
    ALLOWED_TAGS: [
      'a', 'b', 'br', 'div', 'em', 'font', 'h1', 'h2', 'h3', 'hr', 'i',
      'img', 'li', 'ol', 'p', 'span', 'strong', 'table', 'tbody', 'td',
      'th', 'tr', 'u', 'ul', 'center', 'small',
    ],
    ALLOW_DATA_ATTR: false,
    FORBID_TAGS: ['script', 'iframe', 'object', 'embed', 'form', 'input'],
  });
}
