// Generated from specs/001-m1-web-app/contracts/openapi.yaml. Do not edit.
export interface paths {
    "/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
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
                    content?: never;
                };
            };
        };
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/today": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Server date in Europe/Zurich, game number, and which levels have a set. */
        get: {
            parameters: {
                query?: never;
                header?: never;
                path?: never;
                cookie?: never;
            };
            requestBody?: never;
            responses: {
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": {
                            /** Format: date */
                            date: string;
                            gameNumber: number;
                            /** Format: date */
                            weekStart: string;
                            levels: {
                                level?: components["schemas"]["Level"];
                                ready?: boolean;
                            }[];
                        };
                    };
                };
            };
        };
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/plays": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Start or resume a play. Idempotent for the same player, date, level and mode. */
        post: {
            parameters: {
                query?: never;
                header: {
                    "X-Player-Id": components["parameters"]["PlayerId"];
                };
                path?: never;
                cookie?: never;
            };
            requestBody?: {
                content: {
                    "application/json": {
                        level: components["schemas"]["Level"];
                        /** @enum {string} */
                        mode: "daily" | "replay";
                        /**
                         * Format: date
                         * @description Defaults to today. Past dates only with mode replay or a challengeId.
                         */
                        date?: string;
                        /**
                         * @description Ignored when resuming.
                         * @default false
                         */
                        relaxed?: boolean;
                        challengeId?: string;
                    };
                };
            };
            responses: {
                /** @description Existing play */
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["PlayState"];
                    };
                };
                /** @description New play */
                201: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["PlayState"];
                    };
                };
                400: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["Error"];
                    };
                };
                /** @description No set for that date and level (code not_ready). */
                404: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content?: never;
                };
                /** @description mode=replay for today while the daily play of that date and level is not finished (code conflict). */
                409: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content?: never;
                };
            };
        };
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/plays/{playId}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: {
            parameters: {
                query?: never;
                header: {
                    "X-Player-Id": components["parameters"]["PlayerId"];
                };
                path: {
                    playId: components["parameters"]["PlayId"];
                };
                cookie?: never;
            };
            requestBody?: never;
            responses: {
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["PlayState"];
                    };
                };
                404: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["Error"];
                    };
                };
            };
        };
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/plays/{playId}/relaxed": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Switch the play to relaxed from the next answer on. One-way; calling it again is a no-op. */
        post: {
            parameters: {
                query?: never;
                header: {
                    "X-Player-Id": components["parameters"]["PlayerId"];
                };
                path: {
                    playId: components["parameters"]["PlayId"];
                };
                cookie?: never;
            };
            requestBody?: never;
            responses: {
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["PlayState"];
                    };
                };
            };
        };
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/plays/{playId}/questions/{index}/open": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Return question index without its answer; records servedAt the first time only. */
        post: {
            parameters: {
                query?: never;
                header: {
                    "X-Player-Id": components["parameters"]["PlayerId"];
                };
                path: {
                    playId: components["parameters"]["PlayId"];
                    index: components["parameters"]["Index"];
                };
                cookie?: never;
            };
            requestBody?: never;
            responses: {
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["QuestionView"];
                    };
                };
                /** @description Previous question not answered yet. */
                409: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content?: never;
                };
            };
        };
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/plays/{playId}/questions/{index}/answer": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Grade an answer. The same answer again returns the stored result (duplicate true). */
        post: {
            parameters: {
                query?: never;
                header: {
                    "X-Player-Id": components["parameters"]["PlayerId"];
                };
                path: {
                    playId: components["parameters"]["PlayId"];
                    index: components["parameters"]["Index"];
                };
                cookie?: never;
            };
            requestBody?: {
                content: {
                    "application/json": components["schemas"]["AnswerRequest"];
                };
            };
            responses: {
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["AnswerResult"];
                    };
                };
                /** @description Unknown choice, line missing or outside the served code, question not opened. */
                400: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content?: never;
                };
                /** @description A different answer was already recorded; the stored result is returned so the UI can show it. */
                409: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": {
                            /** @constant */
                            code: "conflict";
                            recorded: components["schemas"]["AnswerResult"];
                        };
                    };
                };
                /** @description Temporary storage failure after retries; counted as a scoring failure. Safe to retry. */
                503: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content?: never;
                };
            };
        };
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/practice/next": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: {
            parameters: {
                query?: never;
                header: {
                    "X-Player-Id": components["parameters"]["PlayerId"];
                };
                path?: never;
                cookie?: never;
            };
            requestBody?: {
                content: {
                    "application/json": {
                        level: components["schemas"]["Level"];
                        deck?: string;
                        /** @description Only honoured for questions in the past practice pool of this level and deck. */
                        prefer?: string[];
                    };
                };
            };
            responses: {
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": {
                            attemptId: string;
                            qid: string;
                            question: components["schemas"]["QuestionView"];
                        };
                    };
                };
            };
        };
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/practice/{attemptId}/answer": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: {
            parameters: {
                query?: never;
                header: {
                    "X-Player-Id": components["parameters"]["PlayerId"];
                };
                path: {
                    attemptId: string;
                };
                cookie?: never;
            };
            requestBody?: {
                content: {
                    "application/json": components["schemas"]["AnswerRequest"];
                };
            };
            responses: {
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": components["schemas"]["AnswerResult"];
                    };
                };
                /** @description A different answer was already recorded for this attempt. */
                409: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content?: never;
                };
            };
        };
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/challenges": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create (or return the existing) challenge for a finished play. */
        post: {
            parameters: {
                query?: never;
                header: {
                    "X-Player-Id": components["parameters"]["PlayerId"];
                };
                path?: never;
                cookie?: never;
            };
            requestBody?: {
                content: {
                    "application/json": {
                        playId: string;
                    };
                };
            };
            responses: {
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": {
                            challengeId: string;
                            /** Format: uri */
                            url: string;
                        };
                    };
                };
                /** @description Play not finished. */
                409: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content?: never;
                };
            };
        };
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/challenges/{challengeId}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Challenge as seen by the caller. viewer = owner, colleague_before (owner result shown as
         *     score only, no squares) or colleague_after (both snapshots).
         */
        get: {
            parameters: {
                query?: never;
                header: {
                    "X-Player-Id": components["parameters"]["PlayerId"];
                };
                path: {
                    challengeId: string;
                };
                cookie?: never;
            };
            requestBody?: never;
            responses: {
                200: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content: {
                        "application/json": {
                            /** Format: date */
                            date: string;
                            level: components["schemas"]["Level"];
                            gameNumber: number;
                            /** @enum {string} */
                            viewer: "owner" | "colleague_before" | "colleague_after";
                            ownerScore: number;
                            owner?: components["schemas"]["ResultSnapshot"];
                            you?: components["schemas"]["ResultSnapshot"];
                            /** @description Number of colleagues who finished. */
                            others?: number;
                        };
                    };
                };
                /** @description Unknown */
                404: {
                    headers: {
                        [name: string]: unknown;
                    };
                    content?: never;
                };
            };
        };
        put?: never;
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
        /** @enum {string} */
        Level: "senior" | "starter";
        /** @enum {number} */
        Grade: 0 | 0.5 | 1;
        Error: {
            /** @enum {string} */
            code: "invalid_request" | "not_found" | "not_ready" | "conflict" | "expired" | "rate_limited" | "unavailable";
            message: string;
            requestId?: string;
        };
        Choice: {
            id: string;
            text: string;
        };
        /** @description What the browser sees before answering. Nothing that reveals the answer. */
        QuestionView: {
            index: number;
            deck: string;
            prompt: string;
            code?: string;
            language?: string;
            choices: components["schemas"]["Choice"][];
            /** @description Absent when the play is relaxed. */
            targetSeconds?: number;
            /** Format: date-time */
            servedAt: string;
        };
        AnswerRequest: {
            choiceId: string;
            /** @description Required for spot; the server also checks it is within the served code. */
            line?: number;
        };
        AnswerResult: {
            grade: components["schemas"]["Grade"];
            /** @enum {number} */
            bonus: 0 | 0.2;
            elapsedMs: number;
            correctChoiceId: string;
            correctLines?: number[];
            explanation: string;
            /** Format: uri */
            sourceUrl?: string;
            /** Format: date */
            sourceDate?: string;
            /** @description True when this exact answer was already recorded. */
            duplicate: boolean;
        };
        PlayState: {
            playId: string;
            /** Format: date */
            date: string;
            level: components["schemas"]["Level"];
            /** @enum {string} */
            mode: "daily" | "replay";
            gameNumber: number;
            relaxed: boolean;
            grades: (components["schemas"]["Grade"] | null)[];
            score: number;
            bonus: number;
            elapsedMs?: number;
            finished: boolean;
            challengeId?: string;
            /** @description Next unanswered question, included by POST /plays so the first question needs no extra round trip. */
            question?: components["schemas"]["QuestionView"];
        };
        ResultSnapshot: {
            grades: components["schemas"]["Grade"][];
            score: number;
            bonus: number;
            elapsedMs: number;
            relaxed: boolean;
        };
    };
    responses: never;
    parameters: {
        PlayerId: string;
        PlayId: string;
        Index: number;
    };
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export type operations = Record<string, never>;
