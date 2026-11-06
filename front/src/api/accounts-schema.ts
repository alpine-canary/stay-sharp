// Generated from specs/002-accounts/contracts/accounts.openapi.yaml. Do not edit.
export interface paths {
    "/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** The signed-in account */
        get: {
            parameters: {
                query?: never;
                header?: never;
                path?: never;
                cookie?: never;
            };
            requestBody?: never;
            responses: {
                /** @description OK */
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["Me"];
                    };
                };
                /** @description No account yet for this sign-in (call POST /me/adopt) */
                404: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["Error"];
                    };
                };
                default: components["responses"]["Refused"];
            };
        };
        /** Change the display name */
        put: {
            parameters: {
                query?: never;
                header?: never;
                path?: never;
                cookie?: never;
            };
            requestBody: {
                content: {
                    "application/json": components["schemas"]["MeUpdate"];
                };
            };
            responses: {
                /** @description OK */
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["Me"];
                    };
                };
                /** @description Name refused */
                400: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["Error"];
                    };
                };
                default: components["responses"]["Refused"];
            };
        };
        post?: never;
        /**
         * Delete the account and all its data (FR-114)
         * @description Idempotent. 204 only once every step has finished; 503 with Retry-After if a step failed, and a retry continues.
         */
        delete: {
            parameters: {
                query?: never;
                header?: never;
                path?: never;
                cookie?: never;
            };
            requestBody?: never;
            responses: {
                /** @description Deleted */
                204: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content?: never;
                };
                /** @description Not finished yet, retry */
                503: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["Error"];
                    };
                };
                default: components["responses"]["Refused"];
            };
        };
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/me/adopt": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create the account from this browser, or merge this browser's anonymous history into it */
        post: {
            parameters: {
                query?: never;
                header: {
                    "X-Player-Id": components["parameters"]["PlayerId"];
                };
                path?: never;
                cookie?: never;
            };
            requestBody: {
                content: {
                    "application/json": components["schemas"]["Adopt"];
                };
            };
            responses: {
                /** @description Done (also when repeated) */
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["Adopted"];
                    };
                };
                /** @description The account is being deleted or this browser belongs to another account */
                409: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["Error"];
                    };
                };
                default: components["responses"]["Refused"];
            };
        };
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/me/progress": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** The account's progress copy */
        get: {
            parameters: {
                query?: never;
                header?: never;
                path?: never;
                cookie?: never;
            };
            requestBody?: never;
            responses: {
                /** @description OK */
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["Progress"];
                    };
                };
                default: components["responses"]["Refused"];
            };
        };
        /** Replace the progress copy if nobody changed it since `version` */
        put: {
            parameters: {
                query?: never;
                header?: never;
                path?: never;
                cookie?: never;
            };
            requestBody: {
                content: {
                    "application/json": components["schemas"]["Progress"];
                };
            };
            responses: {
                /** @description Stored; returns the new version */
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["Progress"];
                    };
                };
                /** @description Changed elsewhere; returns the stored copy to merge */
                409: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["Progress"];
                    };
                };
                /** @description Over 64 KB */
                413: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["Error"];
                    };
                };
                default: components["responses"]["Refused"];
            };
        };
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        Me: {
            /** Format: uuid */
            primaryPlayerId: string;
            displayName?: string | null;
            /** Format: date-time */
            createdAt: string;
        };
        MeUpdate: {
            /** @description Letters, digits, space, underscore and hyphen only (checked by the API, see data-model.md); no links, no blocked words. */
            displayName: string | null;
        };
        Adopt: {
            /**
             * @description The player answered "16 or older"; under 16 no request is ever sent.
             * @constant
             */
            adult: true;
        };
        Adopted: {
            /** Format: uuid */
            primaryPlayerId: string;
            /** @description true when this call created the account */
            created: boolean;
            merged: {
                /** @description plays moved from this browser's id */
                plays: number;
                /** @description plays that became unscored replays (same date and level already played) */
                replays: number;
            };
        };
        Progress: {
            version: number;
            body: components["schemas"]["progress.schema"];
        };
        Error: {
            /** @enum {string} */
            code: "invalid_request" | "unauthorized" | "not_found" | "conflict" | "too_large" | "deleting" | "unavailable";
            message: string;
            requestId?: string;
        };
        perLevel: {
            senior: Record<string, never>;
            junior: Record<string, never>;
            starter: Record<string, never>;
        };
        /**
         * Progress copy (the browser's local progress, front/src/storage.ts)
         * @description The player id is not part of the copy: each browser keeps its own until it adopts the account's primary id. The server checks this outline and the 64 KB limit; the browser checks the details with isProgress().
         */
        "progress.schema": {
            /** @constant */
            version: 1;
            /** @enum {unknown} */
            level: "senior" | "junior" | "starter" | null;
            relaxed: boolean;
            /** @description date -> { score, bonus, relaxed } */
            days: components["schemas"]["perLevel"];
            freeze: components["schemas"]["perLevel"];
            longest: {
                senior: number;
                junior: number;
                starter: number;
            };
            deckStats: components["schemas"]["perLevel"];
            practice: components["schemas"]["perLevel"];
            $defs: {
                perLevel: {
                    senior: Record<string, never>;
                    junior: Record<string, never>;
                    starter: Record<string, never>;
                };
            };
        };
    };
    responses: {
        /** @description Refused (invalid request, no or bad token, deleting, unavailable) */
        Refused: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["Error"];
            };
        };
    };
    parameters: {
        PlayerId: string;
    };
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export type operations = Record<string, never>;
