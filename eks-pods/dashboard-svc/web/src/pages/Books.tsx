import { useState } from 'react';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { useOutletContext } from 'react-router-dom';
import { fetchBooks, type Role } from '../api';

const PAGE_SIZE = 50;

export default function Books() {
  const { role } = useOutletContext<{ role: Role }>();
  const [q, setQ] = useState('');
  const [qInput, setQInput] = useState('');
  const [page, setPage] = useState(0);

  const books = useQuery({
    queryKey: ['books', q, page, role],
    queryFn: () => fetchBooks(role, { limit: PAGE_SIZE, offset: page * PAGE_SIZE, q: q || undefined }),
    placeholderData: keepPreviousData,
  });

  const totalPages = books.data ? Math.ceil(books.data.total / PAGE_SIZE) : 0;

  const onSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(0);
    setQ(qInput.trim());
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="h1">도서 카탈로그</h1>
          <p className="text-bf-muted text-xs mt-1">알라딘 OpenAPI 시드 1000책 · books 테이블 직접 조회</p>
        </div>
        <form onSubmit={onSearch} className="flex gap-2">
          <input
            className="ipt w-64"
            placeholder="제목 / 저자 / ISBN13 검색…"
            value={qInput}
            onChange={(e) => setQInput(e.target.value)}
          />
          <button type="submit" className="btn-primary">검색</button>
          {q && (
            <button type="button" className="btn-ghost" onClick={() => { setQ(''); setQInput(''); setPage(0); }}>
              초기화
            </button>
          )}
        </form>
      </div>

      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <span className="label-tag">
            {books.data ? `${books.data.total.toLocaleString()}건 중 ${books.data.offset + 1}–${Math.min(books.data.offset + PAGE_SIZE, books.data.total)}` : ''}
          </span>
          <div className="flex gap-2">
            <button
              className="btn-ghost btn-sm"
              disabled={page === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
            >
              이전
            </button>
            <span className="text-xs text-bf-muted self-center">
              {page + 1} / {Math.max(1, totalPages)}
            </span>
            <button
              className="btn-ghost btn-sm"
              disabled={page + 1 >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              다음
            </button>
          </div>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>ISBN13</th>
              <th>제목</th>
              <th>저자</th>
              <th>출판사</th>
              <th>카테고리</th>
              <th className="text-right">정가</th>
              <th className="text-right">판매가</th>
              <th>상태</th>
            </tr>
          </thead>
          <tbody>
            {books.isLoading && (
              <tr><td colSpan={8} className="text-center py-6 text-bf-muted">로딩 중…</td></tr>
            )}
            {books.data?.items.map((b) => (
              <tr key={b.isbn13}>
                <td className="font-mono text-[11px]">{b.isbn13}</td>
                <td className="font-medium">{b.title}</td>
                <td>{b.author ?? '-'}</td>
                <td>{b.publisher ?? '-'}</td>
                <td className="text-bf-muted">{b.category ?? '-'}</td>
                <td className="text-right">{b.price_standard ? `₩${b.price_standard.toLocaleString()}` : '-'}</td>
                <td className="text-right">{b.price_sales ? `₩${b.price_sales.toLocaleString()}` : '-'}</td>
                <td>
                  {b.discontinue_mode && b.discontinue_mode !== 'NONE'
                    ? <span className="pill-rejected">{b.discontinue_mode}</span>
                    : <span className="pill-approved">판매중</span>}
                </td>
              </tr>
            ))}
            {books.data && books.data.items.length === 0 && (
              <tr><td colSpan={8} className="text-center py-6 text-bf-muted">결과 없음</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
