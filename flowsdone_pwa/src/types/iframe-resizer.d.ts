/**
 * Minimal typings for `iframe-resizer` 4.x (the last MIT release; it ships
 * none). Only what the console uses: resizing an iframe to its content.
 */
declare module 'iframe-resizer' {
  export interface IFrameResizerOptions {
    /** Origins allowed to send size messages. */
    checkOrigin?: boolean | string[]
    log?: boolean
    /** Minimum height in px. */
    minHeight?: number
    /** Milliseconds to wait for the child before warning (0 = never). */
    warningTimeout?: number
  }
  export interface IFrameComponent extends HTMLIFrameElement {
    iFrameResizer?: { removeListeners(): void; close(): void }
  }
  export function iframeResizer(options: IFrameResizerOptions, target: HTMLIFrameElement): IFrameComponent[]
}
