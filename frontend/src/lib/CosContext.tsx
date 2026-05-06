/**
 * CosContext — 管理 STS 临时密钥，提供 cosUrl() 工具函数。
 *
 * 用法：
 *   const { cosUrl } = useCos();
 *   <img src={cosUrl(asset.preview_url)} />
 *
 * cosUrl() 把私有 COS URL 转成带签名的临时 URL。
 * 如果 url 为 null/undefined 或不是 COS 地址，原样返回。
 *
 * 实现：getObjectUrl 是异步回调，使用 Map 缓存签名结果，
 * 完成后通过 setState 触发组件重渲染拿到签名 URL。
 */
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { stsAPI, type StsToken } from "@/lib/api";
import { useAuth } from "@/lib/AuthContext";

type CosCredentials = {
  TmpSecretId: string;
  TmpSecretKey: string;
  SecurityToken: string;
  StartTime: number;
  ExpiredTime: number;
};

type CosClient = {
  getObjectUrl: (
    options: { Bucket: string; Region: string; Key: string; Sign: boolean; Expires: number },
    callback: (err?: unknown, data?: { Url?: string }) => void,
  ) => void;
};

type CosConstructor = new (options: {
  getAuthorization: (options: unknown, callback: (credentials: CosCredentials) => void) => void;
}) => CosClient;

interface CosContextValue {
  cosUrl: (url: string | null | undefined) => string;
  ready: boolean;
}

const CosContext = createContext<CosContextValue>({
  cosUrl: (url) => url ?? "",
  ready: false,
});

export function CosProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const cosRef = useRef<CosClient | null>(null);
  const tokenRef = useRef<StsToken | null>(null);
  const userRef = useRef(user);
  const initPromiseRef = useRef<Promise<void> | null>(null);
  const [ready, setReady] = useState(false);
  // 签名 URL 缓存：原始 URL → 签名 URL
  const [signedCache, setSignedCache] = useState<Map<string, string>>(new Map());
  // 正在请求签名的 URL 集合，避免重复发起
  const pendingRef = useRef<Set<string>>(new Set());

  const initCos = useCallback(async (token: StsToken, shouldAbort: () => boolean = () => false) => {
    tokenRef.current = token;
    const module = await import("cos-js-sdk-v5");
    if (shouldAbort()) return;
    const COS = (module.default ?? module) as CosConstructor;
    cosRef.current = new COS({
      getAuthorization(_options, callback) {
        const t = tokenRef.current!;
        callback({
          TmpSecretId: t.tmpSecretId,
          TmpSecretKey: t.tmpSecretKey,
          SecurityToken: t.sessionToken,
          StartTime: Math.floor(Date.now() / 1000) - (43200 - (t.expiredTime - Math.floor(Date.now() / 1000))),
          ExpiredTime: t.expiredTime,
        });
      },
    });
    setReady(true);
  }, []);

  useEffect(() => {
    userRef.current = user;
    if (!user) {
      cosRef.current = null;
      tokenRef.current = null;
      initPromiseRef.current = null;
      setReady(false);
      setSignedCache(new Map());
      pendingRef.current.clear();
    }
  }, [user]);

  const ensureCos = useCallback(() => {
    if (!userRef.current || cosRef.current || initPromiseRef.current) return;
    initPromiseRef.current = stsAPI.getToken()
      .then((token) => initCos(token, () => !userRef.current))
      .catch((e) => console.warn("[COS] STS 获取失败，图片可能无法显示:", e))
      .finally(() => {
        initPromiseRef.current = null;
      });
  }, [initCos]);

  // 在 token 过期前 5 分钟自动刷新，并清空缓存让图片重新签名
  useEffect(() => {
    if (!ready || !tokenRef.current) return;
    const msLeft = tokenRef.current.expiredTime * 1000 - Date.now() - 5 * 60 * 1000;
    if (msLeft <= 0) return;
    const timer = setTimeout(() => {
      stsAPI.getToken().then((token) => {
        initCos(token, () => !userRef.current);
        // 清空签名缓存，触发重新签名
        setSignedCache(new Map());
        pendingRef.current.clear();
      }).catch(console.warn);
    }, msLeft);
    return () => clearTimeout(timer);
  }, [initCos, ready]);

  const cosUrl = useCallback((url: string | null | undefined): string => {
    if (!url) return "";
    // 只处理 COS 地址
    if (!url.includes(".cos.") || !url.includes(".myqcloud.com")) return url;

    // 已有缓存直接返回
    if (signedCache.has(url)) return signedCache.get(url)!;

    // COS 还未 ready，先返回原始 URL，并按需加载 COS SDK / STS。
    if (!cosRef.current) {
      ensureCos();
      return url;
    }

    // 避免重复发起签名请求
    if (pendingRef.current.has(url)) return url;
    pendingRef.current.add(url);

    try {
      const parsed = new URL(url);
      // host: {bucket}.cos.{region}.myqcloud.com
      const hostParts = parsed.hostname.split(".");
      const bucket = hostParts[0];
      const region = hostParts[2];
      const key = parsed.pathname.slice(1);

      cosRef.current.getObjectUrl(
        { Bucket: bucket, Region: region, Key: key, Sign: true, Expires: 7200 },
        (_err, data) => {
          pendingRef.current.delete(url);
          if (data?.Url) {
            const signedUrl = data.Url;
            setSignedCache((prev) => {
              const next = new Map(prev);
              next.set(url, signedUrl);
              return next;
            });
          }
        }
      );
    } catch {
      pendingRef.current.delete(url);
    }

    // 本次调用返回原始 URL，签名完成后 setState 触发重渲染
    return url;
  }, [ensureCos, signedCache]);

  return (
    <CosContext.Provider value={{ cosUrl, ready }}>
      {children}
    </CosContext.Provider>
  );
}

export function useCos() {
  return useContext(CosContext);
}
