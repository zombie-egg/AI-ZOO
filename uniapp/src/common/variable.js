let defaultLoadingTitle;
// #ifdef MP-TOUTIAO
defaultLoadingTitle = " ";
// #endif
// #ifndef MP-TOUTIAO
defaultLoadingTitle = "";
// #endif
export { defaultLoadingTitle };

export const TAG_POPULAR_KEY_NAME = "popular";
export const LUNA_OSS_BASE_URL =
  import.meta.env.VITE_LUNA_OSS_BASE_URL ||
  "https://iart-user-upload-file.oss-cn-hangzhou.aliyuncs.com";
