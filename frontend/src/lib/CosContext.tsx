/**
 * CosContext — 管理 STS 临时密钥，提供 cosUrl() 工具函数。
 *
 * 用法：
 *   const { cosUrl } = useCos();
 *   <img src={cosUrl(asset.preview_url)} />
 *
 * cosUrl() 把私有 COS URL 转成带签名的临时 URL。
 * 如果 url 为 null/undefined 或不是 COS 地址，原样返回。
 */
import COS from "cos-js-sdk-v5";
import { createContext, useContext, useEffect, useRef, useState } from "react";
import { stsAPI, type StsToken } from "@/lib/api";

interface CosContextValue {
  cosUrl: (url: string | null | undefined) => string;
  ready: boolean;
}

const CosContext = createContext<CosContextValue>({
  cosUrl: (url) => url ?? "",
  ready: false,
});

export function CosProvider({ children }: { children: React.ReactNode }) {
  const cosRef = useRef<InstanceType<typeof COS> | null>(null);
  const tokenRef = useRef<StsToken | null>(null);
  const [ready, setReady] = useState(false);

  const initCos = (token: StsToken) => {
    tokenRef.current = token;
    cosRef.current = new COS({
      getAuthorization(_options, callback) {
        const t = tokenRef.current!;
        callback({
          TmpSecretId: t.tmpSecretId,
          TmpSecretKey: t.tmpSecretKey,
          SecurityToken: t.sessionToken,
          // StartTime: STS 申请时的服务端时间，用当前时间减去剩余秒数估算
          StartTime: Math.floor(Date.now() / 1000) - (43200 - (t.expiredTime - Math.floor(Date.now() / 1000))),
          ExpiredTime: t.expiredTime,
        });
      },
    });
    setReady(true);
  };

  // 初次加载
  useEffect(() => {
    stsAPI.getToken()
      .then(initCos)
      .catch((e) => console.warn("[COS] STS 获取失败，图片可能无法显示:", e));
  }, []);

  // 在 token 过期前 5 分钟自动刷新
  useEffect(() => {
    if (!ready || !tokenRef.current) return;
    const msLeft = tokenRef.current.expiredTime * 1000 - Date.now() - 5 * 60 * 1000;
    if (msLeft <= 0) return;
    const timer = setTimeout(() => {
      stsAPI.getToken().then(initCos).catch(console.warn);
    }, msLeft);
    return () => clearTimeout(timer);
  }, [ready]);

  const cosUrl = (url: string | null | undefined): string => {
    if (!url) return "";
    // 只处理 COS 地址
    if (!url.includes(".cos.") || !url.includes(".myqcloud.com")) return url;
    if (!cosRef.current) return url;

    try {
      const parsed = new URL(url);
      // host: {bucket}.cos.{region}.myqcloud.com
      const hostParts = parsed.hostname.split(".");
      const bucket = hostParts[0];
      const region = hostParts[2];
      const key = parsed.pathname.slice(1);

      // getObjectUrl 是同步返回（Sign:true 时会同步计算签名）
      let signedUrl = url;
      cosRef.current.getObjectUrl(
        { Bucket: bucket, Region: region, Key: key, Sign: true },
        (_err, data) => { if (data?.Url) signedUrl = data.Url; }
      );
      return signedUrl;
    } catch {
      return url;
    }
  };

  return (
    <CosContext.Provider value={{ cosUrl, ready }}>
      {children}
    </CosContext.Provider>
  );
}

export function useCos() {
  return useContext(CosContext);
}
