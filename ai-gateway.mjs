#!/usr/bin/env node
/**
 * AI Gateway Service — Vercel AI Gateway execution engine for Odysseus Orchestrator.
 *
 * Endpoints:
 *   POST /api/execute       — Execute a task, return full result
 *   POST /api/execute/stream — Execute a task, stream result via SSE
 *   GET  /api/models        — List available models
 *   GET  /api/health        — Health check
 *
 * Environment:
 *   VERCEL_OIDC_TOKEN — Vercel OIDC token (from `vc env pull .env.local`)
 *   AI_GATEWAY_PORT   — Port to listen on (default: 3005)
 *   AI_GATEWAY_MODEL  — Default model (default: openai/gpt-4o-mini)
 */

import http from 'http';
import { URL } from 'url';
import { generateText, streamText } from 'ai';

const PORT = parseInt(process.env.AI_GATEWAY_PORT || '3005', 10);
const DEFAULT_MODEL = process.env.AI_GATEWAY_MODEL || 'openai/gpt-4o-mini';

// ─── Helpers ──────────────────────────────────────────────────────────

function json(res, status, data) {
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(data));
}

function parseBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      try { resolve(body ? JSON.parse(body) : {}); }
      catch { reject(new Error('Invalid JSON body')); }
    });
    req.on('error', reject);
  });
}

// ─── Model catalog ────────────────────────────────────────────────────

const AVAILABLE_MODELS = [
  // OpenAI
  'openai/gpt-4o', 'openai/gpt-4o-mini', 'openai/gpt-4-turbo', 'openai/gpt-3.5-turbo',
  // Anthropic
  'anthropic/claude-sonnet-4', 'anthropic/claude-3.5-sonnet', 'anthropic/claude-3-haiku',
  // Google
  'google/gemini-2.5-pro', 'google/gemini-2.5-flash', 'google/gemini-2.0-flash',
  // xAI
  'xai/grok-4', 'xai/grok-3', 'xai/grok-4-fast',
  // Meta
  'meta-llama/llama-4-maverick', 'meta-llama/llama-4-scout',
  'meta-llama/llama-3.3-70b', 'meta-llama/llama-3.1-8b',
  // DeepSeek
  'deepseek/deepseek-r1', 'deepseek/deepseek-v3',
  // Moonshot
  'moonshotai/kimi-k2',
  // Mistral
  'mistral/mistral-large', 'mistral/mistral-small',
  // Qwen
  'qwen/qwen-2.5-72b',
];

// ─── Handlers ─────────────────────────────────────────────────────────

async function handleExecute(req, res) {
  const body = await parseBody(req);
  const task = body.task || body.prompt || '';
  const model = body.model || DEFAULT_MODEL;
  const system = body.system || 'You are a helpful AI assistant. Complete the task concisely and accurately.';
  const maxTokens = body.max_tokens || 4096;
  const temperature = body.temperature ?? 0.7;

  if (!task) {
    return json(res, 400, { error: 'task or prompt is required' });
  }

  const MAX_RETRIES = 3;
  const RETRY_DELAY_MS = 2000;

  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    try {
      const { text, usage } = await generateText({
        model,
        system,
        prompt: task,
        maxTokens,
        temperature,
      });

      return json(res, 200, {
        ok: true,
        model,
        output: text,
        usage: usage ? {
          prompt_tokens: usage.promptTokens,
          completion_tokens: usage.completionTokens,
          total_tokens: usage.totalTokens,
        } : null,
      });
    } catch (err) {
      console.error(`[ai-gateway] attempt ${attempt}/${MAX_RETRIES} failed:`, err.message || err);
      if (attempt < MAX_RETRIES) {
        await new Promise(r => setTimeout(r, RETRY_DELAY_MS * attempt));
      } else {
        return json(res, 502, {
          ok: false,
          error: err.message || String(err),
          model,
          attempts: MAX_RETRIES,
        });
      }
    }
  }
}

async function handleExecuteStream(req, res) {
  const body = await parseBody(req);
  const task = body.task || body.prompt || '';
  const model = body.model || DEFAULT_MODEL;
  const system = body.system || 'You are a helpful AI assistant. Complete the task concisely and accurately.';
  const maxTokens = body.max_tokens || 4096;
  const temperature = body.temperature ?? 0.7;

  if (!task) {
    return json(res, 400, { error: 'task or prompt is required' });
  }

  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
  });

  try {
    const result = streamText({
      model,
      system,
      prompt: task,
      maxTokens,
      temperature,
    });

    for await (const chunk of result.textStream) {
      res.write(`data: ${JSON.stringify({ chunk })}\n\n`);
    }

    res.write(`data: ${JSON.stringify({ done: true })}\n\n`);
    res.end();
  } catch (err) {
    res.write(`data: ${JSON.stringify({ error: err.message || String(err) })}\n\n`);
    res.end();
  }
}

function handleModels(req, res) {
  return json(res, 200, { models: AVAILABLE_MODELS, default: DEFAULT_MODEL });
}

function handleHealth(req, res) {
  return json(res, 200, {
    status: 'ok',
    service: 'ai-gateway',
    default_model: DEFAULT_MODEL,
    models_count: AVAILABLE_MODELS.length,
  });
}

// ─── Router ───────────────────────────────────────────────────────────

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const path = url.pathname;

  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

  try {
    if (path === '/api/execute' && req.method === 'POST') {
      return await handleExecute(req, res);
    }
    if (path === '/api/execute/stream' && req.method === 'POST') {
      return await handleExecuteStream(req, res);
    }
    if (path === '/api/models' && req.method === 'GET') {
      return handleModels(req, res);
    }
    if (path === '/api/health' && req.method === 'GET') {
      return handleHealth(req, res);
    }
    json(res, 404, { error: 'Not found', path });
  } catch (err) {
    json(res, 500, { error: err.message || String(err) });
  }
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`[ai-gateway] listening on http://127.0.0.1:${PORT}`);
  console.log(`[ai-gateway] default model: ${DEFAULT_MODEL}`);
  console.log(`[ai-gateway] ${AVAILABLE_MODELS.length} models available`);
});

export { server };
