<template>
  <div ref="rootRef" class="flex flex-col gap-4 transition-opacity" :class="loading && 'opacity-60'">
    <!-- 页头 -->
    <div class="dash-card fade-up shrink-0 p-4 sm:p-5">
      <div class="flex items-start justify-between gap-4">
        <div>
          <h1 class="text-lg font-semibold text-ink">分组</h1>
          <p class="mt-1 text-sm text-ink-muted">
            把同寝室 / 同班级的账号归到一起。分组有两项用途：绑定图库归属（配置套选「按分组取图」时各组取各自的照片），
            以及把当日的签到结果合并成一条消息推送到对应的 QQ 群——而非每人各发一条。
          </p>
        </div>
        <span class="flex shrink-0 flex-wrap items-center gap-1.5">
          <span class="inline-flex items-center gap-1.5 rounded-full bg-brand/10 px-3 py-1 text-xs font-medium text-brand">
            <Icon name="image" :size="14" />图库归属
          </span>
          <span class="inline-flex items-center gap-1.5 rounded-full bg-brand/10 px-3 py-1 text-xs font-medium text-brand">
            <Icon name="send" :size="14" />合并推送
          </span>
        </span>
      </div>

    </div>

    <!-- 页级筛选：左侧「范围」定看哪类分组，右侧「焦点」定先看哪类问题。
         两者同处一条 bar，焦点计数才能随范围实时可读，而不是另一张卡在偷偷改数字 -->
    <div class="dash-card fade-up flex flex-wrap items-center gap-3 p-3">
      <span class="shrink-0 text-xs text-ink-muted">范围</span>
      <div class="inline-flex shrink-0 rounded-xl bg-cloud/60 p-1">
        <button
          v-for="s in scopes"
          :key="s.key"
          type="button"
          class="rounded-lg px-3.5 py-1.5 text-sm font-medium transition"
          :class="scope === s.key ? 'bg-elevated text-ink shadow-sm' : 'text-ink-muted hover:text-ink'"
          @click="scope = s.key"
        >
          {{ s.label }}
        </button>
      </div>
      <span class="h-5 w-px shrink-0 bg-ink/10"></span>
      <div class="flex flex-wrap items-center gap-2">
        <button
          v-for="f in focusOptions"
          :key="f.key"
          type="button"
          class="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition disabled:opacity-40"
          :class="focus === f.key
            ? 'border-brand/30 bg-brand/10 font-medium text-brand'
            : 'border-transparent bg-ink/5 text-ink-soft hover:bg-ink/10'"
          :disabled="!f.count && focus !== f.key"
          @click="focus = f.key"
        >
          <span class="h-1.5 w-1.5 shrink-0 rounded-full" :class="f.dot"></span>{{ f.label }} {{ f.count }}
        </button>
      </div>
      <span class="ml-auto shrink-0 text-xs text-ink-muted">
        <template v-if="stat.total">今日已签 {{ stat.done }}/{{ stat.total }}<template v-if="stat.fail"> · <span class="text-danger">失败 {{ stat.fail }}</span></template></template>
        <template v-else>今日暂无签到数据</template>
      </span>
    </div>

    <!-- 主从两栏：左分组列表 / 右分组详情（本页无底部分页，整体随内容增高、整页滚动，不锁视口高度） -->
    <div class="flex flex-col gap-4 lg:flex-row lg:items-start">
      <!-- 左：分组列表。搜索留在本卡内——它要按成员姓名 / 学号 / 小北账号穿透到组，
           是列表自己的能力，不该挪到页级去 -->
      <div ref="leftCardRef" class="dash-card fade-up flex flex-col overflow-hidden rounded-2xl lg:w-80 lg:shrink-0">
        <div class="flex items-center justify-between px-4 pt-4">
          <span class="text-sm font-medium text-ink-soft">分组</span>
          <span class="text-xs text-ink-muted">
            <template v-if="filteredGroups.length !== groupsInScope.length">{{ filteredGroups.length }} / </template>{{ groupsInScope.length }} 个
          </span>
        </div>

        <!-- 模糊搜索：姓名 / 学号 / 小北账号 / 分组名，命中即定位到所属分组 -->
        <div class="px-4 pt-3">
          <div class="relative">
            <Icon name="search" :size="16" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
            <input
              v-model="searchQuery"
              type="text"
              placeholder="搜索姓名 / 学号 / 小北账号 / 分组名"
              class="login-input w-full py-2 pl-9 pr-9 text-sm"
            />
            <button
              v-if="searchQuery"
              type="button"
              class="absolute right-2 top-1/2 grid h-6 w-6 -translate-y-1/2 place-items-center rounded-full text-ink-muted transition hover:bg-cloud hover:text-ink"
              aria-label="清除搜索"
              @click="searchQuery = ''"
            >✕</button>
          </div>
        </div>

        <div v-if="groupsInScope.length === 0" class="flex flex-1 flex-col items-center justify-center gap-2 px-4 py-10 text-center text-sm text-ink-muted">
          <Icon :name="scope === 'class' ? 'members' : 'box'" :size="26" class="opacity-50" />
          <span>{{ emptyScopeText }}</span>
        </div>

        <div v-else-if="matchedGroups.length === 0" class="flex flex-1 flex-col items-center justify-center gap-2 px-4 py-10 text-center text-sm text-ink-muted">
          <Icon name="info" :size="26" class="opacity-50" />
          <span>当前范围内没有「{{ focusLabel }}」的分组</span>
        </div>

        <div v-else-if="filteredGroups.length === 0" class="flex flex-1 flex-col items-center justify-center gap-2 px-4 py-10 text-center text-sm text-ink-muted">
          <Icon name="search" :size="26" class="opacity-50" />
          <span>没有分组包含与「{{ searchQuery }}」相关的成员</span>
        </div>

        <div v-else class="p-3">
          <button
            v-for="item in filteredGroups"
            :key="item.group.id ?? item.group.name"
            type="button"
            class="mb-2 w-full rounded-xl border px-3 py-2.5 text-left transition"
            :class="isSelected(item.group) ? 'border-brand/30 bg-brand/10' : 'border-transparent hover:bg-cloud/50'"
            @click="selectGroup(item.group)"
          >
            <div class="flex items-center gap-2">
              <span class="h-2.5 w-2.5 shrink-0 rounded-full" :class="statusDot(item.group.today)" />
              <p class="min-w-0 flex-1 truncate text-sm font-medium text-ink">{{ item.group.name }}</p>
              <span class="shrink-0 text-xs" :class="statusTextClass(item.group.today)">{{ statusShort(item.group.today) }}</span>
            </div>
            <!-- 行尾两枚方点：左=图库归属、右=QQ 群；实心=已绑，虚线琥珀=未绑（计数在筛选条上，明细在详情里） -->
            <div class="mt-1.5 flex items-center gap-2 pl-[18px]">
              <span class="min-w-0 flex-1 truncate text-xs text-ink-muted">
                {{ item.group.memberCount }} 名成员<template v-if="scope === 'all'"> · {{ typeLabel(item.group.type) }}</template>
              </span>
              <span
                class="grid h-5 w-5 shrink-0 place-items-center rounded-md border"
                :class="item.group.imageGroupId
                  ? 'border-brand/35 bg-brand/10 text-brand'
                  : 'border-dashed border-warning/55 bg-warning/5 text-warning'"
                :title="item.group.imageGroupId ? '已绑定图库归属' : '未绑定图库，按配置套兜底取图'"
              >
                <Icon name="image" :size="11" />
              </span>
              <span
                class="grid h-5 w-5 shrink-0 place-items-center rounded-md border"
                :class="item.group.bound
                  ? 'border-brand/35 bg-brand/10 text-brand'
                  : 'border-dashed border-warning/55 bg-warning/5 text-warning'"
                :title="item.group.bound ? '已绑定 QQ 群' : '未绑定 QQ 群，今天不会推送'"
              >
                <Icon name="send" :size="11" />
              </span>
            </div>
            <p v-if="searchQuery && item.hits.length" class="mt-1.5 truncate pl-[18px] text-xs text-brand">
              命中：{{ item.hits.map((h) => h.name || h.account).join('、') }}
            </p>
          </button>
        </div>

        <!-- 新建入口：班级分组由账号的班级字段派生，没有「新建」这回事 -->
        <div v-if="scope !== 'class'" class="border-t border-ink/5 p-3">
          <button
            type="button"
            class="flex w-full items-center justify-center gap-1.5 rounded-xl bg-brand px-3.5 py-2 text-sm font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-dark"
            @click="openCreate"
          >
            <Icon name="plus" :size="17" />新建寝室分组
          </button>
        </div>
      </div>

      <!-- 右：分组详情 -->
      <div ref="rightCardRef" class="dash-card fade-up flex flex-col overflow-hidden rounded-2xl lg:flex-1">
        <div v-if="!selectedGroup" class="flex flex-1 flex-col items-center justify-center gap-2 px-4 py-10 text-center text-sm text-ink-muted">
          <Icon name="send" :size="28" class="opacity-50" />
          <span>从左侧选择一个分组，查看成员与今日推送详情。</span>
        </div>

        <template v-else>
          <div class="p-4 sm:p-5">
            <!-- 头部 -->
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div class="flex flex-wrap items-center gap-2">
                  <h2 class="text-base font-semibold text-ink">{{ selectedGroup.name }}</h2>
                  <span class="rounded-md bg-cloud px-2 py-0.5 text-xs text-ink-muted">{{ typeLabel(selectedGroup.type) }}</span>
                  <span class="rounded-full px-2 py-0.5 text-xs" :class="imageStateBadge.cls">{{ imageStateBadge.text }}</span>
                </div>
                <div class="mt-2"><StatusBadge :today="selectedGroup.today" /></div>
              </div>
              <div class="flex items-center gap-2">
                <button
                  v-if="selectedGroup.bound"
                  type="button"
                  :disabled="flushing"
                  class="inline-flex items-center gap-1.5 rounded-xl bg-brand px-3.5 py-2 text-sm font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-dark disabled:opacity-60"
                  @click="flush(selectedGroup)"
                >
                  <Icon name="send" :size="15" />{{ flushing ? '发送中' : '立即发送' }}
                </button>
                <!-- 未绑 QQ 群是「今天真的不推」，不该是死按钮：点一下直接落到推送段的绑定入口 -->
                <button
                  v-else
                  type="button"
                  class="rounded-xl border border-danger/30 px-3.5 py-2 text-sm font-medium text-danger transition hover:bg-danger/10"
                  @click="detailTab = 'push'"
                >去绑定 QQ 群</button>
                <button
                  v-if="selectedGroup.type === 'dorm'"
                  type="button"
                  class="rounded-xl border border-ink/10 px-3.5 py-2 text-sm font-medium text-danger transition hover:bg-danger/10"
                  @click="askDelete(selectedGroup)"
                >删除</button>
              </div>
            </div>

            <!-- 分段：推送状态在页头已有徽标，取图此前没有任何页级落点，故默认停在取图 -->
            <div class="mt-4 inline-flex rounded-xl bg-cloud/60 p-1">
              <button
                v-for="t in detailTabs"
                :key="t.key"
                type="button"
                class="rounded-lg px-4 py-1.5 text-sm font-medium transition"
                :class="detailTab === t.key ? 'bg-elevated text-ink shadow-sm' : 'text-ink-muted hover:text-ink'"
                @click="detailTab = t.key"
              >
                {{ t.label }}
              </button>
            </div>

            <!-- 取图：把后端的回退链摊开成三级，让人看出本组实际从哪个库取图、以及为什么是它 -->
            <div v-if="detailTab === 'image'" class="mt-4 border-t border-ink/5 pt-4">
              <div class="flex items-center justify-between">
                <p class="text-sm font-medium text-ink-soft">取图归属 · 逐级解析</p>
                <span class="text-xs text-ink-muted">本组 {{ memberList.length }} 人</span>
              </div>

              <div class="mt-3 space-y-1.5">
                <div
                  v-for="t in imageChain.tiers"
                  :key="t.no"
                  class="rounded-lg px-2.5 py-2"
                  :class="tierClass(t)"
                >
                  <div class="flex items-center gap-2">
                    <span class="grid h-4 w-4 shrink-0 place-items-center rounded-full text-[11px]" :class="tierNoClass(t)">{{ t.no }}</span>
                    <span class="min-w-0 flex-1 truncate text-xs" :class="t.tone === 'hit' ? 'text-ink-soft' : 'text-ink-muted'">{{ t.label }}</span>
                    <span class="shrink-0 text-xs font-medium" :class="tierValueClass(t)">{{ t.value }}</span>
                  </div>
                  <p v-if="t.sub" class="mt-0.5 pl-6 text-[11px] text-ink-muted">{{ t.sub }}</p>
                </div>
              </div>

              <div class="mt-2 rounded-lg border px-2.5 py-2 text-xs" :class="imageChain.verdict.cls">
                <template v-if="imageChain.verdict.name">本组从<b class="font-medium">{{ imageChain.verdict.name }}</b>取图<template v-if="imageChain.verdict.count != null"> · {{ imageChain.verdict.count }} 张</template> · {{ imageChain.verdict.note }}</template>
                <template v-else>{{ imageChain.verdict.note }}</template>
              </div>

              <div class="mt-3">
                <p class="text-xs text-ink-muted">本组图库归属</p>
                <div class="mt-1.5 flex items-center gap-2">
                  <BaseSelect v-model="imageDraft" :options="imageGroupOptions" :searchable="true" size="sm" class="w-full" />
                  <template v-if="imageDirty">
                    <button
                      type="button"
                      class="shrink-0 rounded-lg bg-brand px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-brand-dark disabled:opacity-60"
                      :disabled="savingImage"
                      @click="saveImageGroup"
                    >{{ savingImage ? '保存中' : '保存' }}</button>
                    <button
                      type="button"
                      class="shrink-0 rounded-lg border border-ink/10 px-3 py-1.5 text-xs font-medium text-ink-soft transition hover:bg-cloud"
                      @click="resetImageDraft"
                    >取消</button>
                  </template>
                </div>
                <p class="mt-1.5 text-xs text-ink-muted">
                  留空则按上级兜底取图。图库分组在「签到配置 → 我的资源 → 图库」中维护。
                </p>
              </div>
            </div>

            <!-- 推送：QQ 群绑定 + 今日节奏（全组合并成一条） -->
            <div v-else class="mt-4 border-t border-ink/5 pt-4">

              <!-- QQ 群：已绑 → 值 + 编辑；未绑 → 直接把输入框摆出来（今天真的不推，入口不该藏在编辑态里） -->
              <div>
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0">
                    <p class="text-sm font-medium text-ink-soft">QQ 群编码</p>
                    <p v-if="!editingQQ" class="mt-1 truncate text-sm" :class="selectedGroup.bound ? 'text-ink' : 'text-danger'">
                      {{ selectedGroup.bound ? selectedGroup.qqCode : '未绑定 · 今天不会推送' }}
                    </p>
                  </div>
                  <button
                    v-if="selectedGroup.bound && !editingQQ"
                    type="button"
                    class="shrink-0 rounded-lg border border-ink/10 px-3 py-1.5 text-xs font-medium text-ink-soft transition hover:bg-cloud"
                    @click="startEditQQ"
                  >编辑</button>
                </div>
                <div v-if="editingQQ || !selectedGroup.bound" class="mt-2 flex items-center gap-2">
                  <input
                    v-model="qqDraft"
                    type="text"
                    placeholder="如 dorm829"
                    class="login-input w-full py-1.5 text-sm"
                    :class="!selectedGroup.bound && 'border-danger/30'"
                  />
                  <button
                    type="button"
                    class="shrink-0 rounded-lg bg-brand px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-brand-dark disabled:opacity-60"
                    :disabled="savingQQ || !qqDraft.trim()"
                    @click="saveQQ"
                  >{{ savingQQ ? '保存中' : (selectedGroup.bound ? '保存' : '绑定') }}</button>
                  <button
                    v-if="selectedGroup.bound"
                    type="button"
                    class="shrink-0 rounded-lg border border-ink/10 px-3 py-1.5 text-xs font-medium text-ink-soft transition hover:bg-cloud"
                    @click="cancelEditQQ"
                  >取消</button>
                </div>
              </div>

              <div class="mt-3 rounded-xl bg-cloud/40 p-4">
                <p class="mb-3 text-xs font-medium text-ink-muted">今日推送节奏</p>
                <div class="flex items-center">
                  <div class="flex-1 text-center">
                    <div class="mx-auto grid h-7 w-7 place-items-center rounded-full bg-brand/10 text-xs font-semibold text-brand">1</div>
                    <p class="mt-1.5 text-xs text-ink-muted">{{ selectedGroup.memberCount }} 名成员</p>
                  </div>
                  <div class="h-px flex-1 bg-ink/10"></div>
                  <div class="flex-1 text-center">
                    <div class="mx-auto grid h-7 w-7 place-items-center rounded-full text-xs font-semibold" :class="step2Class">{{ step2Label.main }}</div>
                    <p class="mt-1.5 text-xs text-ink-muted">{{ step2Label.sub }}</p>
                  </div>
                  <div class="h-px flex-1 bg-ink/10"></div>
                  <div class="flex-1 text-center">
                    <div class="mx-auto grid h-7 w-7 place-items-center rounded-full text-xs font-semibold" :class="step3Class">{{ step3Glyph }}</div>
                    <p class="mt-1.5 text-xs text-ink-muted">{{ step3Label }}</p>
                  </div>
                </div>
                <p class="mt-3 border-t border-ink/5 pt-3 text-xs text-ink-muted">
                  <template v-if="selectedGroup.bound">{{ selectedGroup.memberCount }} 人的签到结果合并成 <span class="font-medium text-ink">1 条</span> 消息，发往 {{ selectedGroup.qqCode }}</template>
                  <template v-else>绑好 QQ 群后，{{ selectedGroup.memberCount }} 人的结果才会合并发出</template>
                </p>
              </div>
            </div>

            <!-- 成员 -->
            <div class="mt-4 border-t border-ink/5 pt-4">
              <div class="flex items-center justify-between">
                <p class="text-sm font-medium text-ink-soft">成员（{{ memberList.length }}）</p>
                <button
                  v-if="selectedGroup.type === 'dorm'"
                  type="button"
                  class="rounded-lg bg-brand/10 px-3 py-1.5 text-xs font-medium text-brand transition hover:bg-brand/15"
                  @click="openAdd"
                >添加成员</button>
              </div>
              <p v-if="selectedGroup.type === 'class'" class="mt-2 text-xs text-ink-muted">由账号「班级」字段自动归类，成员随账号信息实时更新，无需手动维护。</p>

              <div v-if="memberList.length === 0" class="mt-2 rounded-xl border border-dashed border-ink/10 px-3 py-6 text-center text-sm text-ink-muted">暂无成员</div>
              <div v-else class="mt-3">
                <!-- 寝室：可移除胶囊 -->
                <div v-if="selectedGroup.type === 'dorm'" class="flex flex-wrap gap-2">
                  <span
                    v-for="m in memberList"
                    :key="m.accountId"
                    class="inline-flex items-center gap-2 rounded-full bg-cloud/50 py-1 pl-1 pr-2 text-sm"
                  >
                    <span class="grid h-6 w-6 place-items-center rounded-full bg-brand/10 text-xs font-medium text-brand">{{ initial(m.name || m.account) }}</span>
                    <span class="max-w-[8rem] truncate text-ink">{{ m.name || m.account }}</span>
                    <button
                      type="button"
                      class="shrink-0 text-danger/70 transition hover:text-danger"
                      aria-label="移除成员"
                      @click="askRemoveMember(m)"
                    >✕</button>
                  </span>
                </div>
                <!-- 班级：只读列表 -->
                <div v-else>
                  <div
                    v-for="m in memberList"
                    :key="m.accountId"
                    class="flex items-center gap-3 border-b border-ink/10 py-2 last:border-0"
                  >
                    <span class="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-brand/10 text-xs font-medium text-brand">{{ initial(m.name || m.account) }}</span>
                    <div class="min-w-0">
                      <p class="truncate text-sm text-ink">{{ m.name || m.account }}</p>
                      <p class="truncate text-xs text-ink-muted">{{ m.account }} · {{ m.className || '—' }}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- 新建分组弹窗 -->
    <BaseModal v-model="createOpen" title="新建寝室分组" size="md">
      <div class="space-y-4">
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-soft">分组名称</label>
          <input v-model="createForm.name" type="text" placeholder="如：3栋507" class="login-input w-full py-2 text-sm" />
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-soft">QQ 群编码（qq_code）<span class="text-ink-muted">（可选）</span></label>
          <input v-model="createForm.qqCode" type="text" placeholder="留空可稍后绑定" class="login-input w-full py-2 text-sm" />
          <p class="mt-1.5 text-xs text-ink-muted">未绑定 QQ 群前不会推送；可在右侧详情随时编辑。</p>
        </div>
        <div>
          <label class="mb-1.5 block text-sm font-medium text-ink-soft">图库归属<span class="text-ink-muted">（可选）</span></label>
          <BaseSelect v-model="createForm.imageGroupId" :options="imageGroupOptions" :searchable="true" size="sm" class="w-full" />
          <p class="mt-1.5 text-xs text-ink-muted">配置套图片策略选「按分组取图」时，本组账号按此图库取图；不绑定则走配置套默认图库。</p>
        </div>
      </div>
      <template #footer>
        <button type="button" class="flex-1 rounded-xl border border-ink/10 py-2.5 text-sm font-medium text-ink-soft transition hover:bg-cloud" @click="createOpen = false">取消</button>
        <button
          type="button"
          class="flex-1 rounded-xl bg-brand py-2.5 text-sm font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-dark disabled:opacity-60"
          :disabled="!createForm.name.trim() || creating"
          @click="submitCreate"
        >{{ creating ? '创建中' : '创建' }}</button>
      </template>
    </BaseModal>

    <!-- 添加成员弹窗（单一目的，干净不堆叠） -->
    <BaseModal v-model="addOpen" :title="`添加成员 · ${selectedGroup ? selectedGroup.name : ''}`" size="2xl">
      <div v-if="filteredAddAccounts.length === 0 && !addKeyword" class="py-6 text-center text-sm text-ink-muted">该分组已包含所有可用账号</div>
      <template v-else>
        <div class="relative mb-3 w-full sm:w-72">
          <Icon name="search" :size="16" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
          <input v-model="addKeyword" type="text" placeholder="搜索账号 / 姓名" class="login-input py-2 pl-9 text-sm" />
        </div>
        <div class="xb-scroll max-h-60 overflow-auto rounded-xl border border-ink/5">
          <label
            v-for="a in filteredAddAccounts"
            :key="a.id"
            class="flex cursor-pointer items-center gap-3 border-b border-ink/5 px-3 py-2.5 transition hover:bg-cloud/50"
          >
            <BaseCheckbox :model-value="selectedAccountIds.includes(a.id)" @update:model-value="toggleSelect(a.id, $event)" />
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm text-ink">{{ (a.profile && a.profile.name) || '未命名' }}</p>
              <p class="truncate text-xs text-ink-muted">{{ a.account }} · {{ (a.profile && a.profile.className) || '—' }}</p>
            </div>
          </label>
          <div v-if="filteredAddAccounts.length === 0" class="px-3 py-6 text-center text-sm text-ink-muted">无匹配账号</div>
        </div>
      </template>
      <template #footer>
        <button type="button" class="flex-1 rounded-xl border border-ink/10 py-2.5 text-sm font-medium text-ink-soft transition hover:bg-cloud" @click="addOpen = false">关闭</button>
        <button
          type="button"
          class="flex-1 rounded-xl bg-brand py-2.5 text-sm font-semibold text-white shadow-lg shadow-brand/25 transition hover:bg-brand-dark disabled:opacity-60"
          :disabled="selectedAccountIds.length === 0 || addingMembers"
          @click="submitAddMembers"
        >{{ addingMembers ? '添加中' : `添加 ${selectedAccountIds.length} 人` }}</button>
      </template>
    </BaseModal>

    <!-- 删除确认 -->
    <ConfirmModal
      v-model="deleteOpen"
      title="删除寝室分组"
      :message="deleteTarget ? `确定删除寝室分组「${deleteTarget.name}」？成员关系与图库归属将一并清除（图片本身留在图库中），且不可恢复。` : ''"
      danger
      confirming-text="删除中…"
      @confirm="confirmDelete"
    />

    <!-- 移除成员确认 -->
    <ConfirmModal
      v-model="removeOpen"
      title="移除成员"
      :message="removingMember ? `确定将成员「${removingMember.name || removingMember.account}」从分组「${selectedGroup ? selectedGroup.name : ''}」移除？移除后该成员不再参与本群组的合并推送。` : ''"
      danger
      confirming-text="移除中…"
      @confirm="confirmRemoveMember"
      @cancel="removingMember = null"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import Icon from '@/components/Icon.vue'
import BaseModal from '@/components/BaseModal.vue'
import BaseCheckbox from '@/components/BaseCheckbox.vue'
import BaseSelect from '@/components/BaseSelect.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { toast } from '@/utils/toast'
import { gsap } from 'gsap'
import {
  fetchGroups, createDormGroup, updateDormGroup, deleteDormGroup,
  fetchMembers, addMembers, removeMember, bindClassGroup, flushGroup
} from '@/api/groupPush'
import { fetchAccounts } from '@/api/accounts'
import { fetchConfigSets, fetchImageGroupSummary } from '@/api/signConfig'

// 范围（看哪类分组）：与焦点筛选同处页级一条 bar，焦点计数才能随范围实时可读
const scopes = [
  { key: 'all', label: '全部' },
  { key: 'dorm', label: '寝室' },
  { key: 'class', label: '班级' }
]
const scope = ref('all')

// 焦点（先看哪类问题）：漏网即入口，点一下滤出待补绑的分组
const focus = ref('all')

// 详情分段：推送状态在页头已有徽标，取图此前没有任何页级落点，故默认停在取图
const detailTabs = [
  { key: 'image', label: '取图' },
  { key: 'push', label: '推送' }
]
const detailTab = ref('image')

const loading = ref(false)
const classGroups = ref([])
const dormGroups = ref([])
const allAccounts = ref([])
const selected = ref(null) // { type, key }，key = id ?? name
const flushing = ref(false)

// 新建分组弹窗
const createOpen = ref(false)
const creating = ref(false)
const createForm = ref({ name: '', qqCode: '', imageGroupId: '' })

// QQ 绑定内联编辑
const editingQQ = ref(false)
const qqDraft = ref('')
const savingQQ = ref(false)

// 图库归属：选择器常驻在取图面板里，只有值与已保存的不一致时才出现保存 / 取消
const imageGroups = ref([])
// 「全部图库」的两档张数（各分组之和 + 未分组已含在其中）；口径见 imageGroupCount/imageGroupUsed
const imageTotals = ref({ total: 0, totalUsed: 0 })
const imageDraft = ref('')
const savingImage = ref(false)

// 配置套：取图回退链第 1 级要问「配置套当前是不是按分组取图」，故分组页也得拉一次
const configSets = ref([])

// 图库归属下拉：'' = 不绑定（回退配置套默认图库），其余为「我的资源 → 图库」里建的分组
const imageGroupOptions = computed(() => [
  { label: '不绑定（走配置套默认图库）', value: '' },
  ...imageGroups.value.map((g) => ({ label: g.name, value: g.id }))
])

// 已绑图库的展示名：图库分组被删时后端已自动解绑（ON DELETE SET NULL），此处仅作文案兜底
function imageGroupLabel(id) {
  const g = imageGroups.value.find((x) => String(x.id) === String(id))
  return g ? g.name : '原图库分组已删除'
}

// 「可抽张数」按生效配置套的策略分两档，与配置页 ImageSection::poolOf 同口径：
//   trash/delete：只有 active 能抽（used 属历史残留，永不参与）
//   recycle     ：active 取尽会把 used 整批回池，故 active + used 都算
// 资源接口只给 count/usedCount 两个原始数，策略这一层在这里换算——同一图库可被不同策略的
// 配置套引用，后端替我们选口径就会错。选中分组的那一行已提示本组实际是哪一级在生效。
function imageGroupCount(id) {
  const g = imageGroups.value.find((x) => String(x.id) === String(id))
  return g ? g.count : 0
}

function imageGroupUsed(id) {
  const g = imageGroups.value.find((x) => String(x.id) === String(id))
  return g ? (g.used || 0) : 0
}

function typeLabel(type) {
  return type === 'class' ? '班级' : '寝室'
}

// 成员
const addOpen = ref(false)

// 模糊搜索 + 全量成员索引（用于「搜学生 → 定位所属分组」）
const searchQuery = ref('')
const dormMembersMap = ref({}) // groupId -> [{accountId, account, name, className, studentNo}]
const addingMembers = ref(false)
const addKeyword = ref('')
const selectedAccountIds = ref([])

// 删除确认
const deleteOpen = ref(false)
const deleting = ref(false)
const deleteTarget = ref(null)

// 移除成员二次确认
const removeOpen = ref(false)
const removingMember = ref(null)

// 全部：寝室在前（显式管理、带真实绑定），班级在后（按 className 派生）
const allGroups = computed(() => [...dormGroups.value, ...classGroups.value])
const groupsInScope = computed(() => {
  if (scope.value === 'dorm') return dormGroups.value
  if (scope.value === 'class') return classGroups.value
  return allGroups.value
})

const selectedGroup = computed(() => {
  if (!selected.value) return null
  return groupsInScope.value.find(
    (g) => g.type === selected.value.type && (g.id ?? g.name) === selected.value.key
  ) || null
})

// 班级成员：按 className 实时派生（只读）；寝室：接口拉取
const memberList = computed(() => {
  if (!selectedGroup.value) return []
  const g = selectedGroup.value
  if (g.type === 'dorm') return dormMembersMap.value[g.id] || []
  const name = g.name
  return allAccounts.value
    .filter((a) => (a.profile && a.profile.className) === name)
    .map((a) => ({
      accountId: a.id,
      account: a.account,
      name: (a.profile && a.profile.name) || '',
      className: (a.profile && a.profile.className) || '',
      studentNo: (a.profile && a.profile.studentNo) || ''
    }))
})

const filteredAddAccounts = computed(() => {
  const kw = addKeyword.value.trim().toLowerCase()
  const ids = new Set(memberList.value.map((m) => m.accountId))
  return allAccounts.value
    .filter((a) => !ids.has(a.id))
    .filter((a) => {
      if (!kw) return true
      const name = (a.profile && a.profile.name) || ''
      return a.account.toLowerCase().includes(kw) || name.toLowerCase().includes(kw)
    })
})

// 归一化用于模糊匹配
const norm = (s) => (s == null ? '' : String(s)).toLowerCase().trim()

// 取某分组的全量成员（班级按 className 派生；寝室读预载的成员索引）
function membersOf(g) {
  if (g.type === 'dorm') return dormMembersMap.value[g.id] || []
  return allAccounts.value
    .filter((a) => (a.profile && a.profile.className) === g.name)
    .map((a) => ({
      accountId: a.id,
      account: a.account,
      name: (a.profile && a.profile.name) || '',
      className: (a.profile && a.profile.className) || '',
      studentNo: (a.profile && a.profile.studentNo) || ''
    }))
}

// 焦点口径：缺图库 = 没绑图库归属（还有兜底可走，故不按失败论）；缺 QQ 群 = 今天真的不推
const focusCounts = computed(() => {
  const list = groupsInScope.value
  return {
    all: list.length,
    noImage: list.filter((g) => !g.imageGroupId).length,
    noQQ: list.filter((g) => !g.bound).length,
    unsent: list.filter((g) => !g.today || g.today.status === 'fail').length
  }
})

const matchedGroups = computed(() => {
  const list = groupsInScope.value
  if (focus.value === 'noImage') return list.filter((g) => !g.imageGroupId)
  if (focus.value === 'noQQ') return list.filter((g) => !g.bound)
  if (focus.value === 'unsent') return list.filter((g) => !g.today || g.today.status === 'fail')
  return list
})

const focusOptions = computed(() => {
  const c = focusCounts.value
  return [
    { key: 'all', label: '全部分组', count: c.all, dot: 'bg-brand' },
    { key: 'noImage', label: '缺图库', count: c.noImage, dot: 'bg-warning' },
    { key: 'noQQ', label: '缺 QQ 群', count: c.noQQ, dot: 'bg-danger' },
    { key: 'unsent', label: '今日未推', count: c.unsent, dot: 'bg-ink/30' }
  ]
})

const focusLabel = computed(() => {
  const f = focusOptions.value.find((x) => x.key === focus.value)
  return f ? f.label : '全部分组'
})

const emptyScopeText = computed(() => {
  if (scope.value === 'class') return '暂无班级信息：账号校验通过后会自动带回班级字段。'
  if (scope.value === 'dorm') return '还没有寝室分组，点击下方「新建寝室分组」把同寝室账号归到一起，顺带绑定这个寝室的图库。'
  return '还没有任何分组：账号校验通过后会按班级自动归类，也可以手动新建寝室分组。'
})

// 左侧分组列表：按学生姓名 / 小北账号 / 学号 / 分组名模糊过滤，并回传命中成员
const filteredGroups = computed(() => {
  const q = norm(searchQuery.value)
  const list = matchedGroups.value
  if (!q) return list.map((g) => ({ group: g, hits: [] }))
  const out = []
  for (const g of list) {
    const hits = membersOf(g).filter(
      (m) =>
        norm(m.name).includes(q) ||
        norm(m.account).includes(q) ||
        norm(m.studentNo).includes(q)
    )
    if (hits.length > 0 || norm(g.name).includes(q)) {
      out.push({ group: g, hits: hits.length ? hits : [] })
    }
  }
  return out
})

// 页级汇总：只供筛选条右侧那行元信息，口径跟随「范围」——整条 bar 描述的都是同一个分组集合
const stat = computed(() => {
  let done = 0
  let total = 0
  let fail = 0
  for (const g of groupsInScope.value) {
    const t = g.today
    if (!t) continue
    done += t.memberDone || 0
    total += t.memberTotal || 0
    if (t.status === 'fail') fail += 1
  }
  return { done, total, fail }
})

// 预载所有寝室分组的成员（含学号，便于跨组检索）；账号增删后刷新
async function loadDormMembersMap() {
  const groups = dormGroups.value
  try {
    const entries = await Promise.all(
      groups.map(async (g) => {
        const rows = await fetchMembers(g.id)
        const enriched = rows.map((r) => {
          const acc = allAccounts.value.find((a) => a.id === r.accountId)
          return {
            accountId: r.accountId,
            account: r.account,
            name: r.name,
            className: r.className,
            studentNo: (acc && acc.profile && acc.profile.studentNo) || ''
          }
        })
        return [g.id, enriched]
      })
    )
    dormMembersMap.value = Object.fromEntries(entries)
  } catch (e) {
    /* toast by interceptor */
  }
}

// ── 今日推送节奏步骤条 ──
const step2Label = computed(() => {
  const t = selectedGroup.value && selectedGroup.value.today
  if (t && t.memberTotal > 0) return { main: `${t.memberDone}/${t.memberTotal}`, sub: '已签' }
  return { main: '—', sub: '待签到' }
})
const step2Class = computed(() => {
  const t = selectedGroup.value && selectedGroup.value.today
  if (t && t.memberTotal > 0 && t.memberDone === t.memberTotal) return 'bg-success/10 text-success'
  if (t) return 'bg-warning/10 text-warning'
  return 'bg-ink/10 text-ink-muted'
})
const step3Label = computed(() => {
  const t = selectedGroup.value && selectedGroup.value.today
  if (t && (t.status === 'success' || t.status === 'partial')) return `已推送 ${t.sentAt ? t.sentAt.slice(11) : ''}`
  if (t && t.status === 'fail') return '发送失败'
  return '待推送'
})
const step3Class = computed(() => {
  const t = selectedGroup.value && selectedGroup.value.today
  if (t && t.status === 'success') return 'bg-success/10 text-success'
  if (t && t.status === 'partial') return 'bg-warning/10 text-warning'
  if (t && t.status === 'fail') return 'bg-danger/10 text-danger'
  return 'bg-ink/10 text-ink-muted'
})
const step3Glyph = computed(() => {
  const t = selectedGroup.value && selectedGroup.value.today
  if (t && (t.status === 'success' || t.status === 'partial')) return '✓'
  if (t && t.status === 'fail') return '!'
  return '·'
})

// ── 取图归属：把后端 scheduler.resolve_image_group 的回退链摊开成可见的三级 ──
// 规则：配置套按分组取图（且按本类分组）→ 本组图库归属 → 配置套兜底 groupId（空 = 全部图库）。
// 配置套可以有多个且取图方式未必一致，这里取「生效的那个」作代表，第 1 级副文案里点明共有几个套。
const imageStateBadge = computed(() => {
  const g = selectedGroup.value
  if (!g) return { text: '', cls: '' }
  return g.imageGroupId
    ? { text: `已绑 ${imageGroupLabel(g.imageGroupId)}`, cls: 'bg-success/10 text-success' }
    : { text: '图库未绑', cls: 'bg-warning/10 text-warning' }
})

const imageChain = computed(() => {
  const g = selectedGroup.value
  if (!g) return null
  const isDorm = g.type === 'dorm'
  const kindLabel = isDorm ? '寝室' : '班级'
  const otherLabel = isDorm ? '班级' : '寝室'
  const sets = configSets.value
  const byGroup = sets.filter((s) => s.config.image.mode === 'byGroup')
  const matched = byGroup.filter((s) => s.config.image.groupKind === (isDorm ? 'dorm' : 'class'))
  const rep = matched[0] || byGroup[0] || sets[0] || null
  const groupOn = matched.length > 0
  const bound = !!g.imageGroupId
  // recycle 下 used 取尽会整批回池，故「可抽」= active + used；其余策略只算 active（见 imageGroupCount 注释）
  const recycle = !!rep && rep.config.image.strategy === 'recycle'
  const pool = (id) => imageGroupCount(id) + (recycle ? imageGroupUsed(id) : 0)
  const allPool = () => (imageTotals.value.total || 0) + (recycle ? (imageTotals.value.totalUsed || 0) : 0)
  // 只说「N 张」会让人以为回收站里的也算，故把回池这部分单独点名
  // id 为空 = 回退到「全部图库」，此时张数取自 allPool()，回池量也要按总和算，否则数字被抬高却不说原因
  const usedHint = (id) => {
    const n = recycle ? (id ? imageGroupUsed(id) : (imageTotals.value.totalUsed || 0)) : 0
    return n ? `已用 ${n} 张取尽后自动回池` : ''
  }
  const withHint = (note, id) => [note, usedHint(id)].filter(Boolean).join('；')
  const fallbackId = rep ? rep.config.image.groupId : ''
  const fallbackName = fallbackId ? imageGroupLabel(fallbackId) : '全部图库'
  const fallbackCount = fallbackId ? pool(fallbackId) : (allPool() || null)

  let tier1Sub
  if (!sets.length) tier1Sub = '还没有签到配置套，取图方式未定'
  else if (groupOn) tier1Sub = `按${kindLabel}分组取图 · ${matched.length} 个配置套生效`
  else if (byGroup.length) tier1Sub = `按${otherLabel}分组取图，本组的${kindLabel}归属不参与`
  else tier1Sub = `${sets.length} 个配置套都用固定图库`

  const tiers = [
    {
      no: 1,
      label: '配置套取图方式',
      value: !sets.length ? '暂无配置套' : (byGroup.length ? '按分组取图' : '固定图库'),
      sub: tier1Sub,
      tone: 'neutral'
    },
    {
      no: 2,
      label: '本组图库归属',
      value: bound ? `${imageGroupLabel(g.imageGroupId)} · ${pool(g.imageGroupId)} 张` : '未绑定',
      sub: bound && !groupOn ? '已绑 · 配置套当前不按分组取图，这一级不参与' : '',
      tone: !groupOn ? 'dim' : (bound ? 'hit' : 'warn')
    },
    {
      no: 3,
      label: '配置套兜底图库',
      value: groupOn && bound ? '未参与' : `${fallbackName}${fallbackId ? ` · ${fallbackCount} 张` : ''}`,
      sub: groupOn && bound ? '' : (fallbackId ? '本组未绑时取这个库' : '配置套未指定兜底库，回退到全部图库'),
      tone: groupOn && bound ? 'dim' : 'hit'
    }
  ]

  let verdict
  if (!sets.length) {
    verdict = { name: '', count: null, note: '还没有签到配置套，先建一个才能确定取图方式', cls: 'border-ink/10 bg-ink/[0.03] text-ink-muted' }
  } else if (!groupOn) {
    verdict = { name: fallbackName, count: fallbackCount, note: withHint('配置套没按分组取图，本组归属不生效', fallbackId), cls: 'border-ink/10 bg-ink/[0.03] text-ink-soft' }
  } else if (bound) {
    verdict = { name: imageGroupLabel(g.imageGroupId), count: pool(g.imageGroupId), note: withHint('只取本组照片', g.imageGroupId), cls: 'border-brand/25 bg-brand/10 text-brand' }
  } else {
    verdict = { name: fallbackName, count: fallbackCount, note: withHint(`本组未绑，含其它${kindLabel}的照片`, fallbackId), cls: 'border-warning/30 bg-warning/10 text-warning' }
  }
  return { tiers, verdict }
})

function tierClass(t) {
  if (t.tone === 'hit') return 'border border-brand/30 bg-brand/10'
  if (t.tone === 'warn') return 'border border-dashed border-warning/55 bg-warning/5'
  if (t.tone === 'dim') return 'bg-ink/[0.03] opacity-60'
  return 'bg-ink/[0.03]'
}

function tierNoClass(t) {
  if (t.tone === 'hit') return 'bg-brand/15 text-brand'
  if (t.tone === 'warn') return 'bg-warning/15 text-warning'
  return 'bg-ink/10 text-ink-muted'
}

function tierValueClass(t) {
  if (t.tone === 'hit') return 'text-brand'
  if (t.tone === 'warn') return 'text-warning'
  return 'text-ink-soft'
}

// ── 列表状态 helpers ──
function statusDot(today) {
  if (!today) return 'bg-ink/30'
  if (today.status === 'success') return 'bg-success'
  if (today.status === 'partial') return 'bg-warning'
  return 'bg-danger'
}
function statusTextClass(today) {
  if (!today) return 'text-ink-muted'
  if (today.status === 'success') return 'text-success'
  if (today.status === 'partial') return 'text-warning'
  return 'text-danger'
}
function statusShort(today) {
  if (!today) return '待推送'
  if (today.status === 'success') return '已推送'
  if (today.status === 'partial') return '部分'
  return '发送失败'
}
function initial(name) {
  return (name || '?').trim().charAt(0).toUpperCase()
}

function isSelected(g) {
  return !!selected.value && selected.value.type === g.type && selected.value.key === (g.id ?? g.name)
}

async function loadGroups() {
  loading.value = true
  try {
    const [cls, dorm] = await Promise.all([fetchGroups('class'), fetchGroups('dorm')])
    classGroups.value = cls.map((g) => ({ ...g, _qq: g.qqCode }))
    dormGroups.value = dorm.map((g) => ({ ...g, _qq: g.qqCode }))
    ensureSelection()
  } catch (e) {
    /* toast by interceptor */
  } finally {
    loading.value = false
  }
}

async function loadAccounts() {
  try {
    allAccounts.value = await fetchAccounts()
  } catch (e) {
    /* toast by interceptor */
  }
}

async function loadImageGroups() {
  try {
    const res = await fetchImageGroupSummary()
    imageGroups.value = res.items
    imageTotals.value = { total: res.total, totalUsed: res.totalUsed }
  } catch (e) {
    /* toast by interceptor */
  }
}

async function loadConfigSets() {
  try {
    const { userConfigSets } = await fetchConfigSets()
    configSets.value = userConfigSets
  } catch (e) {
    /* toast by interceptor */
  }
}

function ensureSelection() {
  const list = groupsInScope.value
  if (list.length === 0) {
    selected.value = null
    return
  }
  // 命中判据带上 name：班级分组行首次落库后 id ?? name 由「名字」变「id」，
  // 只比 key 会让刚绑完 QQ / 图库的这次刷新把选中项弹走
  if (selected.value && list.some((g) => g.type === selected.value.type &&
    ((g.id ?? g.name) === selected.value.key || g.name === selected.value.key))) {
    return
  }
  selectGroup(list[0])
}

function selectGroup(g) {
  selected.value = { type: g.type, key: g.id ?? g.name }
  editingQQ.value = false
  qqDraft.value = ''
}

function startEditQQ() {
  qqDraft.value = selectedGroup.value.qqCode || ''
  editingQQ.value = true
}
function cancelEditQQ() {
  editingQQ.value = false
  qqDraft.value = ''
}

// 取图选择器常驻：草稿只在用户真的改了值时才与已保存值不同，据此控制保存 / 取消的出现
const imageDirty = computed(() => {
  const g = selectedGroup.value
  if (!g) return false
  return imageDraft.value !== (g.imageGroupId == null ? '' : String(g.imageGroupId))
})

function resetImageDraft() {
  const g = selectedGroup.value
  imageDraft.value = g && g.imageGroupId != null ? String(g.imageGroupId) : ''
}
async function saveImageGroup() {
  if (!selectedGroup.value) return
  savingImage.value = true
  try {
    const imageGroupId = imageDraft.value === '' ? null : imageDraft.value
    if (selectedGroup.value.type === 'dorm') {
      await updateDormGroup(selectedGroup.value.id, { imageGroupId })
    } else {
      // 班级分组可能尚未落库（没绑 QQ 时没有行），接口按 (type=class, name) upsert
      await bindClassGroup({ name: selectedGroup.value.name, imageGroupId })
    }
    toast('图库归属已保存', 'success')
    await loadGroups()
  } catch (e) {
    /* toast by interceptor */
  } finally {
    savingImage.value = false
  }
}
async function saveQQ() {
  if (!selectedGroup.value) return
  savingQQ.value = true
  try {
    const code = qqDraft.value.trim()
    if (selectedGroup.value.type === 'dorm') {
      await updateDormGroup(selectedGroup.value.id, { qqCode: code })
    } else {
      await bindClassGroup({ name: selectedGroup.value.name, qqCode: code })
    }
    toast('已保存', 'success')
    editingQQ.value = false
    await loadGroups()
  } catch (e) {
    /* toast by interceptor */
  } finally {
    savingQQ.value = false
  }
}

async function flush(g) {
  flushing.value = g.id
  try {
    const res = await flushGroup({ type: g.type, id: g.id, name: g.name })
    const t = res && res.today
    toast(t ? `已发送（${statusShort(t)}）` : '已触发发送', 'success')
    await loadGroups()
  } catch (e) {
    /* toast by interceptor */
  } finally {
    flushing.value = null
  }
}

function openCreate() {
  createForm.value = { name: '', qqCode: '', imageGroupId: '' }
  createOpen.value = true
}
async function submitCreate() {
  creating.value = true
  try {
    await createDormGroup({
      name: createForm.value.name.trim(),
      qqCode: createForm.value.qqCode.trim(),
      imageGroupId: createForm.value.imageGroupId || null
    })
    toast('分组已创建', 'success')
    createOpen.value = false
    await loadGroups()
    await loadDormMembersMap()
  } catch (e) {
    /* toast by interceptor */
  } finally {
    creating.value = false
  }
}

function askDelete(g) {
  deleteTarget.value = g
  deleteOpen.value = true
}
async function confirmDelete() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await deleteDormGroup(deleteTarget.value.id)
    toast('已删除', 'success')
    if (isSelected(deleteTarget.value)) selected.value = null
    deleteOpen.value = false
    await loadGroups()
    await loadDormMembersMap()
  } catch (e) {
    /* toast by interceptor */
  } finally {
    deleting.value = false
  }
}

function openAdd() {
  addKeyword.value = ''
  selectedAccountIds.value = []
  addOpen.value = true
}
function toggleSelect(id, checked) {
  if (checked) {
    if (!selectedAccountIds.value.includes(id)) selectedAccountIds.value = [...selectedAccountIds.value, id]
  } else {
    selectedAccountIds.value = selectedAccountIds.value.filter((x) => x !== id)
  }
}
async function submitAddMembers() {
  if (!selectedGroup.value) return
  addingMembers.value = true
  try {
    const ids = selectedAccountIds.value
    const res = await addMembers(selectedGroup.value.id, ids)
    toast(`已添加 ${res && res.added != null ? res.added : ids.length} 人`, 'success')
    selectedAccountIds.value = []
    addOpen.value = false
    await loadDormMembersMap()
    await loadGroups()
  } catch (e) {
    /* toast by interceptor */
  } finally {
    addingMembers.value = false
  }
}
async function removeMemberFromGroup(id) {
  if (!selectedGroup.value) return
  try {
    await removeMember(selectedGroup.value.id, id)
    await loadDormMembersMap()
    await loadGroups()
  } catch (e) {
    /* toast by interceptor */
  }
}

// 寝室成员移除：先弹二次确认，确认后再真正调用接口（避免误触把人移出分组）
function askRemoveMember(m) {
  removingMember.value = m
  removeOpen.value = true
}
async function confirmRemoveMember() {
  if (!removingMember.value) return
  await removeMemberFromGroup(removingMember.value.accountId)
  removeOpen.value = false
  removingMember.value = null
}

// 范围 / 焦点变化：筛选把当前选中项滤掉时，跟着落到第一个命中分组（否则右侧会忽然空掉）
watch([scope, focus], () => {
  if (norm(searchQuery.value)) {
    const m = filteredGroups.value
    if (m.length) selectGroup(m[0].group)
    else ensureSelection()
    return
  }
  if (matchedGroups.value.some((g) => isSelected(g))) return
  if (matchedGroups.value.length) selectGroup(matchedGroups.value[0])
  else ensureSelection()
})

// 仅一个命中分组时直接选中（搜学生 → 定位分组一步到位）
watch(searchQuery, (q) => {
  const nq = norm(q)
  if (!nq) {
    ensureSelection()
    return
  }
  const m = filteredGroups.value
  if (m.length === 1) selectGroup(m[0].group)
})

// 取图草稿跟随选中项：常驻选择器比原来的「编辑态」更容易把上一个分组的选择带过去，
// 故切分组与保存后刷新都把草稿复位到当前值
watch(
  () => {
    const g = selectedGroup.value
    return g ? `${g.type}|${g.id ?? g.name}|${g.imageGroupId ?? ''}` : ''
  },
  () => {
    resetImageDraft()
    editingQQ.value = false
    qqDraft.value = ''
  }
)

// GSAP 高度过渡：切分组 / 成员增减 / 切 tab / 搜索过滤都会改变卡片高度，
// 这里把「高度跳变」补成平滑过渡。复用项目的高度补间范式：
// 在 DOM 重排前（watch 默认 flush:'pre'）量出旧盒高 → nextTick 后量出新盒高 →
// fromTo 锁到旧高再补到新高，onComplete clearProps 交还类上的自适应高度。
// 尊重 prefers-reduced-motion；作用域限定到根节点、卸载时 revert 回收。
// 注意：本块引用的 selectedGroup / memberList / filteredGroups 均在上方先定义，
// 必须排在它们之后，否则 setup 阶段 watch 取初值会触发 TDZ（ComputedRef 未初始化即访问）。
const rootRef = ref(null)
const leftCardRef = ref(null)
const rightCardRef = ref(null)
let animCtx = null
const reduceMotion =
  typeof window !== 'undefined' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

function animateHeight(el) {
  if (!el || !animCtx || reduceMotion) return
  const prev = el.getBoundingClientRect().height
  nextTick().then(() => {
    if (!el.isConnected) return
    const next = el.getBoundingClientRect().height
    if (Math.abs(prev - next) < 0.5) return
    animCtx.add(() => {
      gsap.fromTo(
        el,
        { height: prev },
        {
          height: next,
          duration: 0.34,
          ease: 'power2.out',
          overwrite: true,
          onComplete: () => gsap.set(el, { clearProps: 'height' })
        }
      )
    })
  })
}

// 高度变化的「结构签名」：命中才触发补间，避免无关响应式更新反复量高
const rightAnimKey = computed(() => {
  const g = selectedGroup.value
  const id = g ? g.id ?? g.name : 'none'
  const bind = g ? `${g.qqCode || ''}|${g.imageGroupId || ''}` : ''
  return `${id}|${memberList.value.length}|${detailTab.value}|${editingQQ.value ? 1 : 0}|${imageDirty.value ? 1 : 0}|${bind}|${configSets.value.length}`
})
const leftAnimKey = computed(() => `${scope.value}|${focus.value}|${filteredGroups.value.length}`)

watch(rightAnimKey, () => animateHeight(rightCardRef.value))
watch(leftAnimKey, () => animateHeight(leftCardRef.value))

onMounted(async () => {
  // GSAP 上下文：作用域限定到组件根，卸载时统一 revert 回收所有补间，避免内存泄漏
  if (rootRef.value) {
    animCtx = gsap.context(() => {}, rootRef.value)
  }
  await Promise.all([loadGroups(), loadAccounts(), loadImageGroups(), loadConfigSets()])
  await loadDormMembersMap()
})

onUnmounted(() => {
  animCtx?.revert()
})
</script>
