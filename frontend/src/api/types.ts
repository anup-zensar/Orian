// Friendly aliases over the generated schema (src/api/schema.d.ts, never hand-edited).
import type { components } from './schema';

type S = components['schemas'];

export type User = S['UserOut'];
export type Me = S['MeOut'];
export type Reference = S['ReferenceOut'];
