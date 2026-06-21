/**
 * services/faceRecognitionService.ts
 * ──────────────────────────────────
 * Integration layer between the Odysseus Node.js backend and the
 * Python ArcFace face recognition microservice.
 *
 * Provides:
 *  - HTTP client for the face-service API
 *  - Keyframe extraction orchestration
 *  - Batch face detection pipeline
 *  - Performer gallery management
 *  - Background scan queue processing
 *  - Ollama vision fallback for ambiguous faces
 *
 * Communication: Node.js → Python service via HTTP (localhost:8050)
 * Fallback: Ollama vision model for unknown face description
 */

import { createReadStream, existsSync } from 'node:fs'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import path from 'node:path'
import { createHash } from 'node:crypto'
import type { Database } from 'better-sqlite3'

// ── Configuration ────────────────────────────────────────────────────────
const FACE_SERVICE_URL = process.env.FACE_SERVICE_URL || 'http://127.0.0.1:8050'
const OLLAMA_BASE_URL = process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434'
const OLLAMA_VISION_MODEL = process.env.OLLAMA_VISION_MODEL || 'llava:latest'

const FACE_MATCH_THRESHOLD = parseFloat(process.env.FACE_MATCH_THRESHOLD || '0.35')
const FACE_CLUSTER_THRESHOLD = parseFloat(process.env.FACE_CLUSTER_THRESHOLD || '0.50')
const FACE_MIN_CONFIDENCE = parseFloat(process.env.FACE_MIN_CONFIDENCE || '0.60')
const KEYFRAME_INTERVAL_SEC = parseInt(process.env.KEYFRAME_INTERVAL_SEC || '5', 10)
const KEYFRAME_MAX_PER_VIDEO = parseInt(process.env.KEYFRAME_MAX_PER_VIDEO || '20', 10)

const REQUEST_TIMEOUT_MS = 30_000
const BATCH_SIZE = 5  // Process 5 keyframes at a time

// ── Types ────────────────────────────────────────────────────────────────
export interface FaceDescriptor {
  bbox: [number, number, number, number]
  confidence: number
  landmarks: [number, number][]
  descriptor: number[]  // 512-dim
}

export interface DetectionResult {
  faces: FaceDescriptor[]
  imageWidth: number
  imageHeight: number
  processingTimeMs: number
}

export interface Performer {
  id: string
  slug: string
  name: string
  aliases: string[]
  gender: string | null
  thumbnail: string | null
  faceCount: number
  videoCount: number
  detectionCount: number
  quality: number
  descriptor: number[] | null
  categories: string[]
  tags: string[]
  favorite: boolean
  folderPath: string | null
  createdAt: string
  updatedAt: string
  lastSeenAt: string | null
}

export interface PerformerVideo {
  id: string
  performerId: string
  videoId: string
  confidence: number
  faceCount: number
  firstSeenSec: number
  lastSeenSec: number
  projections: string[]
}

export interface FaceCluster {
  id: string
  clusterIndex: number
  faceCount: number
  centroidDescriptor: number[]
  avgConfidence: number
  avgQuality: number
  performerId: string | null
  scanSessionId: string
}

export interface ScanQueueItem {
  id: string
  videoId: string
  status: 'pending' | 'processing' | 'done' | 'error'
  priority: number
  source: string
  facesFound: number
  performersMatched: number
  clustersCreated: number
  errorMessage: string | null
}

export interface ScanSession {
  id: string
  status: 'running' | 'completed' | 'cancelled' | 'error'
  totalVideos: number
  processedVideos: number
  totalFacesFound: number
  totalClustersCreated: number
  totalPerformersMatched: number
  config: Record<string, unknown>
  startedAt: string
  completedAt: string | null
}

// ── HTTP client ──────────────────────────────────────────────────────────
async function faceServiceRequest<T>(
  method: 'GET' | 'POST',
  endpoint: string,
  body?: FormData | Record<string, unknown>,
  timeout = REQUEST_TIMEOUT_MS,
): Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)

  try {
    const init: RequestInit = {
      method,
      signal: controller.signal,
    }

    if (body instanceof FormData) {
      init.body = body
    } else if (body) {
      init.headers = { 'Content-Type': 'application/json' }
      init.body = JSON.stringify(body)
    }

    const resp = await fetch(`${FACE_SERVICE_URL}${endpoint}`, init)

    if (!resp.ok) {
      const text = await resp.text().catch(() => '')
      throw new Error(`Face service ${endpoint} → ${resp.status}: ${text}`)
    }

    return resp.json() as Promise<T>
  } finally {
    clearTimeout(timer)
  }
}

// ── Service class ────────────────────────────────────────────────────────
export class FaceRecognitionService {
  private db: Database
  private dataDir: string

  constructor(db: Database, dataDir: string) {
    this.db = db
    this.dataDir = dataDir
  }

  // ── Health check ─────────────────────────────────────────────────────
  async healthCheck(): Promise<{ healthy: boolean; modelLoaded: boolean; uptime: number }> {
    try {
      const h = await faceServiceRequest<{ status: string; model_loaded: boolean; uptime_sec: number }>(
        'GET', '/api/health', undefined, 5000,
      )
      return { healthy: h.status !== 'degraded', modelLoaded: h.model_loaded, uptime: h.uptime_sec }
    } catch {
      return { healthy: false, modelLoaded: false, uptime: 0 }
    }
  }

  // ── Single image detection ───────────────────────────────────────────
  async detectFaces(imagePath: string, maxFaces = 10): Promise<DetectionResult> {
    const data = await readFile(imagePath)
    const form = new FormData()
    form.append('file', new Blob([data]), path.basename(imagePath))
    form.append('max_faces', String(maxFaces))

    return faceServiceRequest<DetectionResult>('POST', '/api/faces/detect', form)
  }

  // ── Keyframe extraction ──────────────────────────────────────────────
  async extractKeyframes(videoPath: string): Promise<{
    keyframes: Array<{ timestampSec: number; tempPath: string; width: number; height: number }>
    durationSec: number
  }> {
    const form = new FormData()
    form.append('video_path', videoPath)
    form.append('interval_sec', String(KEYFRAME_INTERVAL_SEC))
    form.append('max_frames', String(KEYFRAME_MAX_PER_VIDEO))

    const result = await faceServiceRequest<{
      keyframes: Array<{ timestamp_sec: number; temp_path: string; width: number; height: number }>
      duration_sec: number
    }>('POST', '/api/keyframes/extract', form, 120_000)  // 2min timeout for video processing

    return {
      keyframes: result.keyframes.map(k => ({
        timestampSec: k.timestamp_sec,
        tempPath: k.temp_path,
        width: k.width,
        height: k.height,
      })),
      durationSec: result.duration_sec,
    }
  }

  // ── Batch detection pipeline ─────────────────────────────────────────
  async detectFacesInKeyframes(
    keyframePaths: string[],
    onProgress?: (done: number, total: number) => void,
  ): Promise<Map<string, FaceDescriptor[]>> {
    const results = new Map<string, FaceDescriptor[]>()

    // Process in batches to avoid overwhelming the service
    for (let i = 0; i < keyframePaths.length; i += BATCH_SIZE) {
      const batch = keyframePaths.slice(i, i + BATCH_SIZE)
      const batchResults = await Promise.all(
        batch.map(async (kp) => {
          try {
            const result = await this.detectFaces(kp)
            return { path: kp, faces: result.faces }
          } catch (err) {
            console.error(`Face detection failed for ${kp}:`, err)
            return { path: kp, faces: [] }
          }
        }),
      )

      for (const { path: kp, faces } of batchResults) {
        results.set(kp, faces)
      }

      onProgress?.(Math.min(i + BATCH_SIZE, keyframePaths.length), keyframePaths.length)
    }

    return results
  }

  // ── Face matching ────────────────────────────────────────────────────
  async matchFace(
    descriptor: number[],
    galleryDescriptors: number[][],
    threshold = FACE_MATCH_THRESHOLD,
  ): Promise<Array<{ index: number; similarity: number }>> {
    const result = await faceServiceRequest<{
      matches: Array<{ index: number; similarity: number }>
    }>('POST', '/api/faces/match', {
      descriptor,
      gallery: galleryDescriptors,
      threshold,
    })

    return result.matches
  }

  // ── Clustering ───────────────────────────────────────────────────────
  async clusterFaces(
    descriptors: number[][],
    threshold = FACE_CLUSTER_THRESHOLD,
  ): Promise<Array<{
    clusterId: number
    representativeIdx: number
    memberIndices: number[]
    avgSimilarity: number
  }>> {
    const result = await faceServiceRequest<{
      clusters: Array<{
        cluster_id: number
        representative_idx: number
        member_indices: number[]
        avg_similarity: number
      }>
    }>('POST', '/api/faces/cluster', {
      descriptors,
      threshold,
    })

    return result.clusters.map(c => ({
      clusterId: c.cluster_id,
      representativeIdx: c.representative_idx,
      memberIndices: c.member_indices,
      avgSimilarity: c.avg_similarity,
    }))
  }

  // ── Ollama vision fallback ───────────────────────────────────────────
  async describeFaceWithOllama(imageBase64: string): Promise<string> {
    try {
      const resp = await fetch(`${OLLAMA_BASE_URL}/api/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: OLLAMA_VISION_MODEL,
          prompt: 'Describe the person in this image: gender, approximate age, distinctive features. Return JSON: {"gender":"","age":"","features":""}',
          images: [imageBase64],
          stream: false,
        }),
        signal: AbortSignal.timeout(30_000),
      })

      if (!resp.ok) throw new Error(`Ollama ${resp.status}`)
      const data = await resp.json() as { response: string }
      return data.response
    } catch (err) {
      console.error('Ollama fallback failed:', err)
      return ''
    }
  }

  // ── Performer CRUD ───────────────────────────────────────────────────
  createPerformer(data: {
    name: string
    slug?: string
    gender?: string
    descriptor?: number[]
    thumbnail?: string
  }): Performer {
    const id = crypto.randomUUID()
    const slug = data.slug || this.slugify(data.name)
    const now = new Date().toISOString()

    this.db.prepare(`
      INSERT INTO performers (id, slug, name, gender, descriptor, thumbnail, created_at, updated_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      id, slug, data.name, data.gender || null,
      data.descriptor ? Buffer.from(new Float32Array(data.descriptor).buffer) : null,
      data.thumbnail || null,
      now, now,
    )

    return this.getPerformer(id)!
  }

  getPerformer(id: string): Performer | null {
    const row = this.db.prepare('SELECT * FROM performers WHERE id = ?').get(id) as Record<string, unknown> | undefined
    return row ? this.rowToPerformer(row) : null
  }

  getPerformerBySlug(slug: string): Performer | null {
    const row = this.db.prepare('SELECT * FROM performers WHERE slug = ?').get(slug) as Record<string, unknown> | undefined
    return row ? this.rowToPerformer(row) : null
  }

  listPerformers(opts: {
    limit?: number
    offset?: number
    orderBy?: 'name' | 'video_count' | 'quality' | 'created_at'
    favoriteOnly?: boolean
    search?: string
  } = {}): { performers: Performer[]; total: number } {
    const {
      limit = 50, offset = 0,
      orderBy = 'video_count', favoriteOnly = false, search,
    } = opts

    let where = 'WHERE 1=1'
    const params: unknown[] = []

    if (favoriteOnly) {
      where += ' AND favorite = 1'
    }
    if (search) {
      where += ' AND (name LIKE ? OR aliases LIKE ?)'
      params.push(`%${search}%`, `%${search}%`)
    }

    const total = this.db.prepare(`SELECT COUNT(*) as n FROM performers ${where}`).get(...params) as { n: number }

    const validOrder: Record<string, string> = {
      name: 'name COLLATE NOCASE',
      video_count: 'video_count DESC',
      quality: 'quality DESC',
      created_at: 'created_at DESC',
    }
    const order = validOrder[orderBy] || validOrder.video_count

    const rows = this.db.prepare(
      `SELECT * FROM performers ${where} ORDER BY ${order} LIMIT ? OFFSET ?`
    ).all(...params, limit, offset) as Record<string, unknown>[]

    return {
      performers: rows.map(r => this.rowToPerformer(r)),
      total: total.n,
    }
  }

  updatePerformer(id: string, data: Partial<{
    name: string
    slug: string
    gender: string
    descriptor: number[]
    thumbnail: string
    categories: string[]
    tags: string[]
    favorite: boolean
    notes: string
  }>): Performer | null {
    const sets: string[] = []
    const params: unknown[] = []

    if (data.name !== undefined) { sets.push('name = ?'); params.push(data.name) }
    if (data.slug !== undefined) { sets.push('slug = ?'); params.push(data.slug) }
    if (data.gender !== undefined) { sets.push('gender = ?'); params.push(data.gender) }
    if (data.descriptor !== undefined) {
      sets.push('descriptor = ?')
      params.push(data.descriptor ? Buffer.from(new Float32Array(data.descriptor).buffer) : null)
    }
    if (data.thumbnail !== undefined) { sets.push('thumbnail = ?'); params.push(data.thumbnail) }
    if (data.categories !== undefined) { sets.push('categories = ?'); params.push(JSON.stringify(data.categories)) }
    if (data.tags !== undefined) { sets.push('tags = ?'); params.push(JSON.stringify(data.tags)) }
    if (data.favorite !== undefined) { sets.push('favorite = ?'); params.push(data.favorite ? 1 : 0) }
    if (data.notes !== undefined) { sets.push('notes = ?'); params.push(data.notes) }

    if (sets.length === 0) return this.getPerformer(id)

    sets.push('updated_at = ?')
    params.push(new Date().toISOString())
    params.push(id)

    this.db.prepare(`UPDATE performers SET ${sets.join(', ')} WHERE id = ?`).run(...params)
    return this.getPerformer(id)
  }

  deletePerformer(id: string): boolean {
    const result = this.db.prepare('DELETE FROM performers WHERE id = ?').run(id)
    return result.changes > 0
  }

  // ── Performer video linking ──────────────────────────────────────────
  linkPerformerVideo(data: {
    performerId: string
    videoId: string
    confidence: number
    faceCount: number
    firstSeenSec?: number
    lastSeenSec?: number
    projections?: string[]
  }): void {
    const id = crypto.randomUUID()
    const now = new Date().toISOString()

    this.db.prepare(`
      INSERT OR REPLACE INTO performer_videos
        (id, performer_id, video_id, confidence, face_count, first_seen_sec, last_seen_sec, projections, created_at, updated_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      id, data.performerId, data.videoId, data.confidence, data.faceCount,
      data.firstSeenSec || 0, data.lastSeenSec || 0,
      JSON.stringify(data.projections || []),
      now, now,
    )
  }

  getPerformerVideos(performerId: string): PerformerVideo[] {
    const rows = this.db.prepare(
      'SELECT * FROM performer_videos WHERE performer_id = ? ORDER BY confidence DESC'
    ).all(performerId) as Record<string, unknown>[]

    return rows.map(r => ({
      id: r.id as string,
      performerId: r.performer_id as string,
      videoId: r.video_id as string,
      confidence: r.confidence as number,
      faceCount: r.face_count as number,
      firstSeenSec: r.first_seen_sec as number,
      lastSeenSec: r.last_seen_sec as number,
      projections: JSON.parse(r.projections as string || '[]'),
    }))
  }

  // ── Scan queue management ────────────────────────────────────────────
  enqueueVideo(videoId: string, priority = 0, source = 'manual'): string {
    const id = crypto.randomUUID()
    const now = new Date().toISOString()

    this.db.prepare(`
      INSERT INTO face_scan_queue (id, video_id, status, priority, source, created_at, updated_at)
      VALUES (?, ?, 'pending', ?, ?, ?, ?)
    `).run(id, videoId, priority, source, now, now)

    return id
  }

  dequeuePending(limit = 5): ScanQueueItem[] {
    const rows = this.db.prepare(`
      SELECT * FROM face_scan_queue
      WHERE status = 'pending'
      ORDER BY priority DESC, created_at ASC
      LIMIT ?
    `).all(limit) as Record<string, unknown>[]

    return rows.map(r => ({
      id: r.id as string,
      videoId: r.video_id as string,
      status: r.status as ScanQueueItem['status'],
      priority: r.priority as number,
      source: r.source as string,
      facesFound: r.faces_found as number,
      performersMatched: r.performers_matched as number,
      clustersCreated: r.clusters_created as number,
      errorMessage: r.error_message as string | null,
    }))
  }

  updateQueueItem(id: string, data: Partial<{
    status: ScanQueueItem['status']
    facesFound: number
    performersMatched: number
    clustersCreated: number
    errorMessage: string
    workerId: string
  }>): void {
    const sets: string[] = []
    const params: unknown[] = []

    if (data.status !== undefined) { sets.push('status = ?'); params.push(data.status) }
    if (data.facesFound !== undefined) { sets.push('faces_found = ?'); params.push(data.facesFound) }
    if (data.performersMatched !== undefined) { sets.push('performers_matched = ?'); params.push(data.performersMatched) }
    if (data.clustersCreated !== undefined) { sets.push('clusters_created = ?'); params.push(data.clustersCreated) }
    if (data.errorMessage !== undefined) { sets.push('error_message = ?'); params.push(data.errorMessage) }
    if (data.workerId !== undefined) { sets.push('worker_id = ?'); params.push(data.workerId) }

    if (data.status === 'processing') { sets.push('started_at = ?'); params.push(new Date().toISOString()) }
    if (data.status === 'done' || data.status === 'error') { sets.push('completed_at = ?'); params.push(new Date().toISOString()) }

    sets.push('updated_at = ?')
    params.push(new Date().toISOString())
    params.push(id)

    this.db.prepare(`UPDATE face_scan_queue SET ${sets.join(', ')} WHERE id = ?`).run(...params)
  }

  // ── Scan sessions ────────────────────────────────────────────────────
  createScanSession(totalVideos: number): string {
    const id = crypto.randomUUID()
    const now = new Date().toISOString()

    this.db.prepare(`
      INSERT INTO face_scan_sessions (id, status, total_videos, config, started_at)
      VALUES (?, 'running', ?, ?, ?)
    `).run(id, totalVideos, JSON.stringify({
      matchThreshold: FACE_MATCH_THRESHOLD,
      clusterThreshold: FACE_CLUSTER_THRESHOLD,
      minConfidence: FACE_MIN_CONFIDENCE,
    }), now)

    return id
  }

  updateScanSession(id: string, data: Partial<{
    status: ScanSession['status']
    processedVideos: number
    totalFacesFound: number
    totalClustersCreated: number
    totalPerformersMatched: number
    errorMessage: string
  }>): void {
    const sets: string[] = []
    const params: unknown[] = []

    if (data.status !== undefined) { sets.push('status = ?'); params.push(data.status) }
    if (data.processedVideos !== undefined) { sets.push('processed_videos = ?'); params.push(data.processedVideos) }
    if (data.totalFacesFound !== undefined) { sets.push('total_faces_found = ?'); params.push(data.totalFacesFound) }
    if (data.totalClustersCreated !== undefined) { sets.push('total_clusters_created = ?'); params.push(data.totalClustersCreated) }
    if (data.totalPerformersMatched !== undefined) { sets.push('total_performers_matched = ?'); params.push(data.totalPerformersMatched) }
    if (data.errorMessage !== undefined) { sets.push('error_message = ?'); params.push(data.errorMessage) }
    if (data.status === 'completed' || data.status === 'error') {
      sets.push('completed_at = ?')
      params.push(new Date().toISOString())
    }

    if (sets.length === 0) return
    params.push(id)
    this.db.prepare(`UPDATE face_scan_sessions SET ${sets.join(', ')} WHERE id = ?`).run(...params)
  }

  // ── Full scan pipeline ───────────────────────────────────────────────
  async scanVideo(
    videoId: string,
    videoPath: string,
    scanSessionId: string,
    onProgress?: (stage: string, progress: number) => void,
  ): Promise<{
    facesFound: number
    performersMatched: number
    clustersCreated: number
  }> {
    let facesFound = 0
    let performersMatched = 0
    let clustersCreated = 0

    try {
      // 1. Extract keyframes
      onProgress?.('extracting_keyframes', 0)
      const { keyframes } = await this.extractKeyframes(videoPath)
      onProgress?.('extracting_keyframes', 100)

      if (keyframes.length === 0) {
        return { facesFound: 0, performersMatched: 0, clustersCreated: 0 }
      }

      // 2. Detect faces in all keyframes
      onProgress?.('detecting_faces', 0)
      const keyframePaths = keyframes.map(k => k.tempPath)
      const detectionResults = await this.detectFacesInKeyframes(
        keyframePaths,
        (done, total) => onProgress?.('detecting_faces', Math.round((done / total) * 100)),
      )

      // Collect all detections
      const allDetections: Array<{
        descriptor: number[]
        confidence: number
        timestampSec: number
        keyframePath: string
      }> = []

      for (const [kp, faces] of detectionResults) {
        const kf = keyframes.find(k => k.tempPath === kp)
        for (const face of faces) {
          allDetections.push({
            descriptor: face.descriptor,
            confidence: face.confidence,
            timestampSec: kf?.timestampSec || 0,
            keyframePath: kp,
          })
        }
      }
      facesFound = allDetections.length

      if (facesFound === 0) {
        return { facesFound: 0, performersMatched: 0, clustersCreated: 0 }
      }

      // 3. Match against existing performers
      onProgress?.('matching_performers', 0)
      const knownPerformers = this.listPerformers({ limit: 1000 }).performers
        .filter(p => p.descriptor !== null)

      const performerDescriptors = knownPerformers.map(p => p.descriptor!)
      const matchedPerformerIds = new Set<string>()

      for (const det of allDetections) {
        if (performerDescriptors.length > 0) {
          const matches = await this.matchFace(det.descriptor, performerDescriptors)
          if (matches.length > 0 && matches[0].similarity >= FACE_MATCH_THRESHOLD) {
            const performer = knownPerformers[matches[0].index]
            matchedPerformerIds.add(performer.id)

            // Store face detection
            this.storeFaceDetection({
              videoId,
              performerId: performer.id,
              descriptor: det.descriptor,
              confidence: det.confidence,
              timestampSec: det.timestampSec,
              sourceImage: det.keyframePath,
              scanSessionId,
            })
          }
        }
      }
      performersMatched = matchedPerformerIds.size
      onProgress?.('matching_performers', 100)

      // 4. Cluster unmatched faces
      onProgress?.('clustering', 0)
      const unmatched = allDetections.filter(d => {
        // Simple check: if not matched to a known performer
        return true  // In production, track which ones were matched
      })

      if (unmatched.length >= 3) {
        const descriptors = unmatched.map(d => d.descriptor)
        const clusters = await this.clusterFaces(descriptors)

        for (const cluster of clusters) {
          if (cluster.memberIndices.length < 2) continue  // Skip singletons

          const clusterId = crypto.randomUUID()
          const memberDescriptors = cluster.memberIndices.map(i => unmatched[i].descriptor)
          const centroid = this.computeCentroid(memberDescriptors)

          // Store cluster
          this.db.prepare(`
            INSERT INTO face_clusters (id, cluster_index, face_count, centroid_descriptor, avg_confidence, avg_quality, scan_session_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
          `).run(
            clusterId, cluster.clusterId, cluster.memberIndices.length,
            Buffer.from(new Float32Array(centroid).buffer),
            0.8, 0.7,  // Placeholder — compute from actual data
            scanSessionId,
            new Date().toISOString(), new Date().toISOString(),
          )

          clustersCreated++
        }
      }
      onProgress?.('clustering', 100)

      return { facesFound, performersMatched, clustersCreated }
    } catch (err) {
      console.error(`Scan failed for video ${videoId}:`, err)
      throw err
    }
  }

  // ── Background worker ─────────────────────────────────────────────────
  async processQueue(
    videoPathMap: (videoId: string) => string,
    onProgress?: (videoId: string, stage: string, progress: number) => void,
  ): Promise<void> {
    const sessionId = this.createScanSession(0)
    let totalProcessed = 0
    let totalFaces = 0
    let totalClusters = 0
    let totalPerformers = 0

    while (true) {
      const items = this.dequeuePending(5)
      if (items.length === 0) break

      for (const item of items) {
        this.updateQueueItem(item.id, { status: 'processing', workerId: 'main' })

        try {
          const videoPath = videoPathMap(item.videoId)
          if (!videoPath || !existsSync(videoPath)) {
            this.updateQueueItem(item.id, { status: 'error', errorMessage: 'Video file not found' })
            continue
          }

          const result = await this.scanVideo(
            item.videoId,
            videoPath,
            sessionId,
            (stage, progress) => onProgress?.(item.videoId, stage, progress),
          )

          this.updateQueueItem(item.id, {
            status: 'done',
            facesFound: result.facesFound,
            performersMatched: result.performersMatched,
            clustersCreated: result.clustersCreated,
          })

          totalFaces += result.facesFound
          totalClusters += result.clustersCreated
          totalPerformers += result.performersMatched
          totalProcessed++
        } catch (err) {
          this.updateQueueItem(item.id, {
            status: 'error',
            errorMessage: err instanceof Error ? err.message : String(err),
          })
        }
      }

      this.updateScanSession(sessionId, {
        processedVideos: totalProcessed,
        totalFacesFound: totalFaces,
        totalClustersCreated: totalClusters,
        totalPerformersMatched: totalPerformers,
      })
    }

    this.updateScanSession(sessionId, { status: 'completed' })
  }

  // ── Helpers ───────────────────────────────────────────────────────────
  private storeFaceDetection(data: {
    videoId: string
    performerId: string | null
    descriptor: number[]
    confidence: number
    timestampSec: number
    sourceImage: string
    scanSessionId: string
  }): void {
    const id = crypto.randomUUID()
    this.db.prepare(`
      INSERT INTO face_detections (id, video_id, timestamp_sec, confidence, descriptor, performer_id, source_image, scan_session_id, created_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      id, data.videoId, data.timestampSec, data.confidence,
      Buffer.from(new Float32Array(data.descriptor).buffer),
      data.performerId, data.sourceImage, data.scanSessionId,
      new Date().toISOString(),
    )
  }

  private computeCentroid(descriptors: number[][]): number[] {
    const arr = new Float32Array(512)
    for (const d of descriptors) {
      for (let i = 0; i < 512; i++) arr[i] += d[i]
    }
    // Average
    for (let i = 0; i < 512; i++) arr[i] /= descriptors.length
    // L2 normalize
    let norm = 0
    for (let i = 0; i < 512; i++) norm += arr[i] * arr[i]
    norm = Math.sqrt(norm)
    if (norm > 1e-10) {
      for (let i = 0; i < 512; i++) arr[i] /= norm
    }
    return Array.from(arr)
  }

  private slugify(name: string): string {
    return name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '')
      .slice(0, 64)
  }

  private rowToPerformer(row: Record<string, unknown>): Performer {
    return {
      id: row.id as string,
      slug: row.slug as string,
      name: row.name as string,
      aliases: JSON.parse(row.aliases as string || '[]'),
      gender: row.gender as string | null,
      thumbnail: row.thumbnail as string | null,
      faceCount: (row.face_count as number) || 0,
      videoCount: (row.video_count as number) || 0,
      detectionCount: (row.detection_count as number) || 0,
      quality: (row.quality as number) || 0,
      descriptor: row.descriptor
        ? Array.from(new Float32Array((row.descriptor as Buffer).buffer))
        : null,
      categories: JSON.parse(row.categories as string || '[]'),
      tags: JSON.parse(row.tags as string || '[]'),
      favorite: (row.favorite as number) === 1,
      folderPath: row.folder_path as string | null,
      createdAt: row.created_at as string,
      updatedAt: row.updated_at as string,
      lastSeenAt: row.last_seen_at as string | null,
    }
  }
}

// ── Singleton export ────────────────────────────────────────────────────
let _instance: FaceRecognitionService | null = null

export function getFaceRecognitionService(db: Database, dataDir: string): FaceRecognitionService {
  if (!_instance) {
    _instance = new FaceRecognitionService(db, dataDir)
  }
  return _instance
}
