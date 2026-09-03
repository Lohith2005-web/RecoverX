const BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api';

export async function apiFetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = endpoint.startsWith('http') ? endpoint : `${BASE_URL}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`;
  
  const defaultHeaders = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  };

  const response = await fetch(url, {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  });

  if (!response.ok) {
    const errorBody = await response.text();
    let errorMessage = `API Error (${response.status}): ${response.statusText}`;
    try {
      const parsed = JSON.parse(errorBody);
      if (parsed.detail) {
        errorMessage = typeof parsed.detail === 'string' ? parsed.detail : JSON.stringify(parsed.detail);
      }
    } catch {
      // Use raw text fallback
    }
    throw new Error(errorMessage);
  }

  return response.json() as Promise<T>;
}
