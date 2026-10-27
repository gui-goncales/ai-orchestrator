import React, { useState } from 'react';
import { Check, Copy } from 'lucide-react';

interface MarkdownProps {
  content: string;
  className?: string;
}

export function MarkdownRenderer({ content, className = '' }: MarkdownProps) {
  if (!content) return null;

  // Split content by code blocks first
  const parts: React.ReactNode[] = [];
  const codeBlockRegex = /```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  let blockIdx = 0;
  while ((match = codeBlockRegex.exec(content)) !== null) {
    const textBefore = content.substring(lastIndex, match.index);
    if (textBefore) {
      parts.push(<TextMarkdown key={`text-${blockIdx}`} text={textBefore} />);
    }

    const language = match[1] || 'text';
    const code = match[2];
    parts.push(
      <CodeBlock key={`code-${blockIdx}`} language={language} code={code} />
    );

    lastIndex = match.index + match[0].length;
    blockIdx++;
  }

  const remainingText = content.substring(lastIndex);
  if (remainingText) {
    parts.push(<TextMarkdown key={`text-final`} text={remainingText} />);
  }

  return <div className={`ai-markdown-body ${className}`}>{parts}</div>;
}

function CodeBlock({ language, code }: { language: string; code: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="chat-code-block">
      <div className="chat-code-header">
        <span className="chat-code-lang">{language.toLowerCase()}</span>
        <button
          type="button"
          className="chat-code-copy"
          onClick={handleCopy}
          title="Copiar código"
        >
          {copied ? (
            <>
              <Check size={13} className="text-green" />
              <span>Copiado!</span>
            </>
          ) : (
            <>
              <Copy size={13} />
              <span>Copiar</span>
            </>
          )}
        </button>
      </div>
      <pre className="chat-code-content">
        <code>{code.replace(/\n$/, '')}</code>
      </pre>
    </div>
  );
}

function TextMarkdown({ text }: { text: string }) {
  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];
  let inList = false;
  let listItems: React.ReactNode[] = [];
  let listType: 'ul' | 'ol' = 'ul';

  const flushList = (key: string) => {
    if (listItems.length > 0) {
      if (listType === 'ul') {
        elements.push(<ul key={key} className="chat-ul">{listItems}</ul>);
      } else {
        elements.push(<ol key={key} className="chat-ol">{listItems}</ol>);
      }
      listItems = [];
      inList = false;
    }
  };

  lines.forEach((line, index) => {
    const trimmed = line.trim();

    // Headers
    if (line.startsWith('### ')) {
      flushList(`flush-${index}`);
      elements.push(<h4 key={index} className="chat-h3">{formatInline(line.slice(4))}</h4>);
      return;
    }
    if (line.startsWith('## ')) {
      flushList(`flush-${index}`);
      elements.push(<h3 key={index} className="chat-h2">{formatInline(line.slice(3))}</h3>);
      return;
    }
    if (line.startsWith('# ')) {
      flushList(`flush-${index}`);
      elements.push(<h2 key={index} className="chat-h1">{formatInline(line.slice(2))}</h2>);
      return;
    }

    // Blockquote
    if (line.startsWith('> ')) {
      flushList(`flush-${index}`);
      elements.push(
        <blockquote key={index} className="chat-quote">
          {formatInline(line.slice(2))}
        </blockquote>
      );
      return;
    }

    // Unordered List
    if (/^[-*]\s+/.test(trimmed)) {
      if (!inList || listType !== 'ul') {
        flushList(`flush-${index}`);
        inList = true;
        listType = 'ul';
      }
      listItems.push(
        <li key={`li-${index}`}>{formatInline(trimmed.replace(/^[-*]\s+/, ''))}</li>
      );
      return;
    }

    // Ordered List
    if (/^\d+\.\s+/.test(trimmed)) {
      if (!inList || listType !== 'ol') {
        flushList(`flush-${index}`);
        inList = true;
        listType = 'ol';
      }
      listItems.push(
        <li key={`li-${index}`}>{formatInline(trimmed.replace(/^\d+\.\s+/, ''))}</li>
      );
      return;
    }

    // Empty line or regular paragraph
    flushList(`flush-${index}`);
    if (trimmed === '') {
      elements.push(<div key={`empty-${index}`} className="chat-spacer" />);
    } else {
      elements.push(
        <p key={index} className="chat-p">
          {formatInline(line)}
        </p>
      );
    }
  });

  flushList('flush-final');

  return <>{elements}</>;
}

function formatInline(text: string): React.ReactNode {
  // Matches inline code `code`, bold **text**, italic *text*
  const parts: React.ReactNode[] = [];
  const regex = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.substring(lastIndex, match.index));
    }
    const token = match[0];
    if (token.startsWith('`') && token.endsWith('`')) {
      parts.push(
        <code key={key++} className="chat-inline-code">
          {token.slice(1, -1)}
        </code>
      );
    } else if (token.startsWith('**') && token.endsWith('**')) {
      parts.push(<strong key={key++}>{token.slice(2, -2)}</strong>);
    } else if (token.startsWith('*') && token.endsWith('*')) {
      parts.push(<em key={key++}>{token.slice(1, -1)}</em>);
    }
    lastIndex = match.index + token.length;
  }

  if (lastIndex < text.length) {
    parts.push(text.substring(lastIndex));
  }

  return parts.length > 0 ? parts : text;
}
