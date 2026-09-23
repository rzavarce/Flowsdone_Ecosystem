/** Same shape as the Spanish catalog, with every leaf as a plain string. */
export type Messages<T> = { [K in keyof T]: T[K] extends string ? string : Messages<T[K]> }
