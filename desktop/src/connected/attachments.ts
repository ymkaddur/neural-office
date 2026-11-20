import type { Requester } from './client';
import type { Approval } from './model';

export type Attachment = {
  id: string; name: string; kind: string; bytes: number; sha256: string;
  source_id: string; created_at: number; origin: string; status?: string; detail?: string;
};
export type Citation = {
  attachment_id: string; name: string; sha256: string; quote: string;
  kind?: string; code?: string; page?: number; pointer?: string; line?: number; column?: number;
  member?: string; pdf_rect?: number[]; region?: number[]; context?: string; value?: number | string; unit?: string;
};
export type InspectionFinding = {
  rule: string; origin_report?: string; status: 'match' | 'mismatch' | 'insufficient' | 'observed'; total?: number;
  title: string; detail: string; sources: Citation[];
};
export type InspectionStep = {
  at: number; duration_ms: number; actor: string; action: string;
  detail: string; status: string; attachment_id?: string;
};
export type ReviewDecision = {revision: number; choice: 'pdf'|'json'|'defer'; at: number};
export type Inspection = {
  team?: import('../office/team.ts').TeamReview;
  completed_at?: number; decision?: ReviewDecision;
  id: string; project_id: string; thread_id: string; created_at: number; objective: string;
  attachments: Attachment[]; findings: InspectionFinding[]; steps: InspectionStep[];
  reservations: number; model_calls: number;
};
export type ThreadSummary = { id: string; objective: string; created_at: number };
export type InspectionSummary = Pick<Inspection, 'id' | 'project_id' | 'thread_id' | 'objective' | 'created_at'> &
  { attachment_count: number; finding_count: number };
export type AttachmentView = {
  attachment_id: string; name: string; sha256: string; kind: string; status: string; detail: string;
  page?: number; pages?: number; signature?:string; text?: string; image?: string; width?: number; height?: number;
  entries?: { path: string; bytes: number; kind: string; readable: boolean; detail: string }[];
  fields?: { pointer: string; line: number; column?: number; value: unknown; quote?: string }[];
  candidates?: {page: number; value: number; quote: string; context?: string; pdf_rect?: number[]; region?: number[]}[];
  findings?: { code: string; line: number; column: number }[];
  findings_total?: number; text_truncated?: boolean; fields_truncated?: boolean; complete?: boolean;
  text_start_line?: number; text_start_column?: number; total_lines?: number;
  line?: number; column?: number; orientation?: number; original_width?: number; original_height?: number;
  member?: string; member_sha256?: string; member_bytes?: number; container_kind?: string;
};
export type ExcerptApproval = Approval & { thread_id: string; report_id: string; fragments: Citation[] };

export function attachmentApi(send: Requester) {
  const target = (project_id: string, thread_id: string) => ({ project_id, thread_id });
  type Reading = { promise: Promise<unknown>; interrupt?: () => void; project?: unknown; thread?: unknown };
  const pending = new Map<string, Reading>();
  let metadataQueue = Promise.resolve();

  function read<T>(method: string, params: Record<string, unknown>, preview = false): Promise<T> {
    const key = JSON.stringify([method, params]);
    const previous = pending.get(key);
    if (previous) return previous.promise as Promise<T>;
    let interrupted = false;
    const operation = async () => {
      for (const delay of [0, 40, 100, 220, 440]) {
        if (delay) await new Promise<void>(done => setTimeout(done, delay));
        if (interrupted) throw Error('ATTACHMENT_READ_CANCELLED');
        try {
          const result = await send<T>(method, params);
          if (interrupted) throw Error('ATTACHMENT_READ_CANCELLED');
          return result;
        }
        catch (error) {
          const code = error instanceof Error ? error.message : '';
          if (!['HOST_BUSY', 'ATTACHMENT_READER_BUSY'].includes(code) || delay === 440) throw error;
        }
      }
      throw Error('HOST_BUSY');
    };
    // Wait for earlier metadata only; rendering a large PDF never owns this queue.
    const task = (preview ? Promise.resolve() : metadataQueue).then(operation);
    if (!preview) metadataQueue = task.then(() => {}, () => {});
    const entry: Reading = { promise: task };
    if (preview) {
      entry.project = params.project_id;
      entry.thread = params.thread_id;
      entry.interrupt = () => { interrupted = true; };
    }
    pending.set(key, entry);
    const retire = () => { if (pending.get(key) === entry) pending.delete(key); };
    task.then(retire, retire);
    return task;
  }

  return {
    threads: (project_id: string) => read<ThreadSummary[]>('attachments.threads', { project_id }),
    pick: (project: string, thread: string) => send<Attachment[]>('attachments.pick', target(project, thread)),
    list: (project: string, thread: string) => read<Attachment[]>('attachments.list', target(project, thread)),
    cancel: (project: string, thread: string) => {
      for (const [key, entry] of pending) {
        if (entry.interrupt && entry.project === project && entry.thread === thread) {
          entry.interrupt();
          pending.delete(key);
        }
      }
      return send<{cancelled: number}>('attachments.cancel', target(project, thread));
    },
    inspect: (project: string, thread: string, attachment_ids: string[], objective: string) =>
      send<Inspection>('attachments.inspect', { ...target(project, thread), attachment_ids, objective }),
    view: (project: string, thread: string, capture_id: string, options: { page?: number; member?: string } = {}) =>
      read<AttachmentView>('attachments.view', { ...target(project, thread), capture_id, page: options.page ?? 1,
        member: options.member ?? '' }, true),
    history: (project: string, thread: string) => read<InspectionSummary[]>('attachments.history', target(project, thread)),
    report: (project: string, thread: string, report_id: string) =>
      read<Inspection>('attachments.report', { ...target(project, thread), report_id }),
    decide: (project: string, thread: string, report_id: string, choice: ReviewDecision['choice'], expected_revision: number) =>
      send<ReviewDecision>('attachments.decide', {...target(project, thread), report_id, choice, expected_revision}),
    preview: (project: string, thread: string, report_id: string, model_digest: string, objective: string) =>
      send<ExcerptApproval>('attachments.preview', { ...target(project, thread), report_id, model_digest, objective }),
  };
}
