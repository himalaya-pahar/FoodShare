# FoodShare AI Assistant — Frontend Integration Guide

This guide details how to integrate the FoodShare AI Assistant service into the frontend application (React Native / Expo / Web).

---

## 1. Architecture & Endpoints

The AI Assistant is integrated directly into the main FoodShare backend API deployed on Vercel. You do **not** need a separate AI server or separate base URL.

| Service | Host | AI Chat Endpoint |
|---|---|---|
| **FoodShare Backend API** | Vercel (`process.env.EXPO_PUBLIC_API_BASE_URL`) | `POST /ai/chat` |

Simply call `POST ${API_BASE_URL}/ai/chat` using your app's existing Vercel API base URL.

---

## 2. Authentication Contract

- **Single Sign-On / Shared JWT:** The AI service uses the exact same JWT access token issued by the Core API (`POST /login`).
- **No separate AI authentication:** Pass the user's existing core token in the HTTP `Authorization` header:
  ```http
  Authorization: Bearer <access_token>
  ```
- **Permissions:** The user account must be `APPROVED` by an admin. Pending or unapproved accounts receive `403 Forbidden`.

---

## 3. API Contract

### Health Check

- **Method:** `GET`
- **Path:** `/health`
- **Headers:** None required
- **Response:**
  ```json
  {
    "status": "ok"
  }
  ```

### Chat Endpoint

- **Method:** `POST`
- **Path:** `/ai/chat`
- **Headers:**
  ```http
  Content-Type: application/json
  Authorization: Bearer <core_api_jwt_token>
  ```

#### Request Payload

```typescript
interface ChatRequest {
  message: string;              // 1 to 1000 characters
  session_id?: string | null;   // null or omit on first turn; pass previous session_id on follow-ups
}
```

Example (Turn 1):
```json
{
  "message": "How do I request a pickup as an NGO?",
  "session_id": null
}
```

Example (Follow-up Turn):
```json
{
  "message": "What happens if another NGO already requested it?",
  "session_id": "b132808b-6bb3-42e8-9844-325b3ea66a3f"
}
```

#### Response Payload

```typescript
interface ChatResponse {
  session_id: string;        // UUID string to save in chat state for follow-ups
  answer: string;            // Markdown-formatted grounded assistant response
  sources: [];               // Deprecated compatibility field; always empty
  scope_decision: "in_domain" | "out_of_domain" | "no_evidence";
}
```

Example response:
```json
{
  "session_id": "b132808b-6bb3-42e8-9844-325b3ea66a3f",
  "answer": "To request a pickup as an NGO, browse available donations on the Available Donations screen and submit a request with your estimated pickup time. The restaurant will review your request and can accept or reject it.",
  "sources": [],
  "scope_decision": "in_domain"
}
```

---

## 4. Status Codes & Error Handling

| Code | Meaning | Recommended Frontend Action |
|---|---|---|
| `200 OK` | Successful response | Render `answer`. The legacy `sources` field is always empty. Save `session_id` in state. |
| `401 Unauthorized` | Invalid or expired token | Trigger existing app re-login or token refresh. |
| `403 Forbidden` | Account not yet approved | Display friendly notice: "Your account is awaiting administrator approval." |
| `422 Unprocessable Entity` | Validation error (e.g. empty message, >1000 chars, malformed UUID) | Show inline input validation alert. |
| `500 / 503 / Network` | Server error or cold start | Display: "AI assistant is temporarily unavailable. Please try again." with retry button. |

---

## 5. TypeScript / React Native Reference Implementation

### API Client (`services/aiApi.ts`)

```typescript
export interface ChatResponse {
  session_id: string;
  answer: string;
  sources: [];
  scope_decision: 'in_domain' | 'out_of_domain' | 'no_evidence';
}

const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL;

export async function sendChatMessage(
  message: string,
  sessionId: string | null,
  token: string
): Promise<ChatResponse> {
  const trimmed = message.trim();
  if (!trimmed) {
    throw new Error('Message cannot be empty');
  }
  if (trimmed.length > 1000) {
    throw new Error('Message cannot exceed 1000 characters');
  }

  const response = await fetch(`${API_BASE_URL}/ai/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
      'Accept': 'application/json',
    },
    body: JSON.stringify({
      message: trimmed,
      session_id: sessionId || null,
    }),
  });

  if (response.status === 401) {
    throw new Error('SESSION_EXPIRED');
  }
  if (response.status === 403) {
    throw new Error('ACCOUNT_NOT_APPROVED');
  }
  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    throw new Error(errorData?.detail || `AI service error (${response.status})`);
  }

  return response.json();
}
```

### React Hook (`hooks/useAiChat.ts`)

```typescript
import { useState, useCallback } from 'react';
import { sendChatMessage } from '../services/aiApi';

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  timestamp: Date;
}

export function useAiChat(authToken: string | null) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      sender: 'assistant',
      text: 'Hello! I am the FoodShare Assistant. Ask me anything about donation guidelines, pickup workflows, or platform policies.',
      timestamp: new Date(),
    },
  ]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!authToken) {
        setError('Please log in to chat with the assistant.');
        return;
      }

      const userMsg: ChatMessage = {
        id: `user-${Date.now()}`,
        sender: 'user',
        text,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMsg]);
      setLoading(true);
      setError(null);

      try {
        const data = await sendChatMessage(text, sessionId, authToken);
        setSessionId(data.session_id);

        const aiMsg: ChatMessage = {
          id: `ai-${Date.now()}`,
          sender: 'assistant',
          text: data.answer,
          timestamp: new Date(),
        };

        setMessages((prev) => [...prev, aiMsg]);
      } catch (err: any) {
        if (err.message === 'SESSION_EXPIRED') {
          setError('Your login session expired. Please log in again.');
        } else if (err.message === 'ACCOUNT_NOT_APPROVED') {
          setError('Your account is awaiting approval by an administrator.');
        } else {
          setError(err.message || 'Failed to reach AI Assistant.');
        }
      } finally {
        setLoading(false);
      }
    },
    [authToken, sessionId]
  );

  const resetChat = useCallback(() => {
    setSessionId(null);
    setMessages([
      {
        id: `welcome-${Date.now()}`,
        sender: 'assistant',
        text: 'Chat reset. How can I help you with FoodShare today?',
        timestamp: new Date(),
      },
    ]);
    setError(null);
  }, []);

  return {
    messages,
    loading,
    error,
    sendMessage,
    resetChat,
  };
}
```

---

## 6. Frontend Environment Configuration

In the frontend repository's environment configuration (e.g. `.env`, `.env.development`, `.env.production`):

```env
# Unified FoodShare API (Vercel)
EXPO_PUBLIC_API_BASE_URL=https://your-core-api.vercel.app
```

The AI Assistant endpoints (`POST /ai/chat`, `GET /health`) run on the exact same base URL as the rest of the FoodShare API.

