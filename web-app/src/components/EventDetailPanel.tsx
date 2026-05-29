import { useState, useEffect, useCallback } from "react";
import type { MapEvent, Comment } from "../types/api";
import { fetchComments, postComment } from "../services/commentApi";

interface EventDetailPanelProps {
  event: MapEvent;
  onClose: () => void;
}

function timeAgo(isoStr: string): string {
  if (!isoStr) return "";
  const diff = Date.now() - new Date(isoStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "剛剛";
  if (mins < 60) return `${mins} 分鐘前`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} 小時前`;
  return `${Math.floor(hrs / 24)} 天前`;
}

export default function EventDetailPanel({ event, onClose }: EventDetailPanelProps) {
  const [comments, setComments] = useState<Comment[]>([]);
  const [loading, setLoading] = useState(true);
  const [author, setAuthor] = useState("匿名");
  const [content, setContent] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // 載入留言
  useEffect(() => {
    let cancelled = false;
    fetchComments(event.id)
      .then((data) => {
        if (!cancelled) {
          setComments(data);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [event.id]);

  const handleSubmit = useCallback(async () => {
    if (!content.trim()) return;
    setSubmitting(true);
    try {
      const newComment = await postComment(event.id, {
        author: author.trim() || "匿名",
        content: content.trim(),
      });
      setComments((prev) => [newComment, ...prev]);
      setContent("");
    } catch {
      // silent
    } finally {
      setSubmitting(false);
    }
  }, [event.id, author, content]);

  return (
    <div className="detail-panel-overlay" onClick={onClose}>
      <div className="detail-panel" onClick={(e) => e.stopPropagation()}>
        {/* 標頭 */}
        <div className="detail-header">
          <div className="detail-badge-row">
            <span className={`detail-severity ${event.severity}`}>
              {event.severity === "urgent" ? "緊急" : "一般"}
            </span>
            {event.created_at && (
              <span className="detail-time">{timeAgo(event.created_at)}</span>
            )}
          </div>
          <h3>{event.title}</h3>
          {event.message && <p className="detail-message">{event.message}</p>}
          {event.distance_meters != null && (
            <small className="detail-distance">
              距離 {Math.round(event.distance_meters)} 公尺
            </small>
          )}
          <button className="detail-close" onClick={onClose}>✕</button>
        </div>

        {/* 留言區 */}
        <div className="detail-comments">
          <h4>留言 ({comments.length})</h4>
          {loading ? (
            <p className="comments-loading">載入中...</p>
          ) : comments.length === 0 ? (
            <p className="comments-empty">目前沒有留言</p>
          ) : (
            <div className="comments-list">
              {comments.map((c) => (
                <div key={c.comment_id} className="comment-item">
                  <div className="comment-meta">
                    <strong>{c.author}</strong>
                    <span>{timeAgo(c.created_at)}</span>
                  </div>
                  <p>{c.content}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 新增留言 */}
        <div className="comment-form">
          <div className="comment-form-row">
            <input
              type="text"
              value={author}
              onChange={(e) => setAuthor(e.target.value)}
              placeholder="暱稱"
              maxLength={30}
              className="comment-author"
            />
            <input
              type="text"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="寫下你的留言..."
              maxLength={500}
              className="comment-input"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit();
                }
              }}
            />
            <button
              onClick={handleSubmit}
              disabled={submitting || !content.trim()}
              className="comment-submit"
            >
              {submitting ? "..." : "送出"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
