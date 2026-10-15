// 分享卡片在网页版里触发浏览器下载（ShareCard.cs）
mergeInto(LibraryManager.library, {
  MercyDownload: function (ptr, length, namePtr) {
    var bytes = HEAPU8.slice(ptr, ptr + length);
    var blob = new Blob([bytes], { type: "image/png" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = UTF8ToString(namePtr);
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  }
});
